"""Response ownership for synchronous native OCI streams."""

import asyncio
import unittest
from unittest.mock import patch

import httpx
from litellm.exceptions import MidStreamFallbackError

from payload_fixture import event
from http_fixture import Exchange, SyncBody, URL, complete

MODULE = "litellm.llms.oci.chat.transformation"


class SyncHTTPClosure(unittest.TestCase):
    def exchange(self, fragments, status=200):
        exchange = Exchange(SyncBody(fragments), status=status)
        self.addCleanup(exchange.close)
        return exchange

    def assert_released(self, exchange):
        self.assertEqual(exchange.body.close_started, 1)
        self.assertEqual(exchange.body.close_completed, 1)
        self.assertTrue(exchange.responses[0].is_closed)
        self.assertFalse(exchange.handler.client.is_closed)
        self.assertEqual(exchange.handler.client.get(URL.replace("/20231130/actions/chat", "/again")).text, "alive")

    def test_success_and_length_release_response(self):
        for reason, ending in (("COMPLETE", "stop"), ("STOP", "stop"), ("MAX_TOKENS", "length")):
            with self.subTest(reason=reason):
                exchange = self.exchange(complete(reason))
                stream = exchange.sync_stream()
                try:
                    chunks = list(stream)
                    self.assertEqual([c.choices[0].finish_reason for c in chunks], [None, ending])
                finally:
                    asyncio.run(stream.aclose())
                self.assert_released(exchange)

    def test_close_before_first_read_is_idempotent(self):
        exchange = self.exchange(complete())
        stream = exchange.sync_stream()
        asyncio.run(stream.aclose())
        asyncio.run(stream.aclose())
        self.assert_released(exchange)

    def test_close_after_one_chunk_releases_response(self):
        exchange = self.exchange(complete())
        stream = exchange.sync_stream()
        self.assertEqual(next(stream).choices[0].delta.content, "BILLING")
        asyncio.run(stream.aclose())
        self.assert_released(exchange)

    def test_rejected_streams_release_without_success(self):
        scenarios = {
            "empty": [], "premature": [event("BILLING").encode()],
            "error": [event(finish="ERROR").encode()],
            "malformed": [b"data: {broken\n\n"],
            "read_failure": [event("BILLING").encode(), httpx.ReadError("synthetic read failure")],
        }
        for name, fragments in scenarios.items():
            with self.subTest(name=name):
                exchange = self.exchange(fragments)
                stream = exchange.sync_stream()
                chunks = []
                try:
                    with self.assertRaises(MidStreamFallbackError):
                        for chunk in stream:
                            chunks.append(chunk)
                finally:
                    asyncio.run(stream.aclose())
                self.assertFalse(any(c.choices[0].finish_reason == "stop" for c in chunks))
                self.assert_released(exchange)

    def test_constructor_failure_releases_acquired_response(self):
        exchange = self.exchange(complete())
        with patch(MODULE + ".OCIStreamWrapper", side_effect=RuntimeError("synthetic handoff")):
            with self.assertRaisesRegex(RuntimeError, "synthetic handoff"):
                exchange.sync_stream()
        self.assert_released(exchange)

    def test_non200_success_status_releases_rejected_response(self):
        exchange = self.exchange(complete(), status=201)
        # Preserve the pin's pre-existing unread-text rejection; test ownership.
        with self.assertRaises(httpx.ResponseNotRead):
            exchange.sync_stream()
        self.assert_released(exchange)

    def test_close_failure_preserves_original_constructor_failure(self):
        exchange = self.exchange(complete())
        with patch(MODULE + ".OCIStreamWrapper", side_effect=RuntimeError("synthetic handoff")):
            with patch.object(httpx.Response, "close", side_effect=OSError("synthetic close")) as close:
                with self.assertRaisesRegex(RuntimeError, "synthetic handoff"):
                    exchange.sync_stream()
                close.assert_called_once()

    def test_iterator_close_failure_still_releases_response(self):
        class BrokenIterator:
            def __iter__(self):
                return self

            def __next__(self):
                raise StopIteration

            def close(self):
                raise RuntimeError("synthetic iterator close")

        exchange = self.exchange(complete())
        with patch(MODULE + "._iter_sse_events", return_value=BrokenIterator()):
            stream = exchange.sync_stream()
        asyncio.run(stream.aclose())
        self.assert_released(exchange)

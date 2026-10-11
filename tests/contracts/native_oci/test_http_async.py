"""Response ownership for asynchronous native OCI streams."""

import unittest
from unittest.mock import patch

import httpx
from litellm.exceptions import MidStreamFallbackError

from payload_fixture import event
from http_fixture import AsyncBody, Exchange, URL, complete

MODULE = "litellm.llms.oci.chat.transformation"


class AsyncHTTPClosure(unittest.IsolatedAsyncioTestCase):
    def exchange(self, fragments, status=200):
        exchange = Exchange(AsyncBody(fragments), asynchronous=True, status=status)
        self.addAsyncCleanup(exchange.aclose)
        return exchange

    async def assert_released(self, exchange):
        self.assertEqual(exchange.body.close_started, 1)
        self.assertEqual(exchange.body.close_completed, 1)
        self.assertTrue(exchange.responses[0].is_closed)
        self.assertFalse(exchange.handler.client.is_closed)
        alive = await exchange.handler.client.get(URL.replace("/20231130/actions/chat", "/again"))
        self.assertEqual(alive.text, "alive")

    async def test_success_and_length_release_response(self):
        for reason, ending in (("COMPLETE", "stop"), ("STOP", "stop"), ("MAX_TOKENS", "length")):
            with self.subTest(reason=reason):
                exchange = self.exchange(complete(reason))
                stream = await exchange.async_stream()
                try:
                    chunks = [chunk async for chunk in stream]
                    self.assertEqual([c.choices[0].finish_reason for c in chunks], [None, ending])
                finally:
                    await stream.aclose()
                await self.assert_released(exchange)

    async def test_close_before_first_read_is_idempotent(self):
        exchange = self.exchange(complete())
        stream = await exchange.async_stream()
        await stream.aclose()
        await stream.aclose()
        await self.assert_released(exchange)

    async def test_close_after_one_chunk_releases_response(self):
        exchange = self.exchange(complete())
        stream = await exchange.async_stream()
        self.assertEqual((await anext(stream)).choices[0].delta.content, "BILLING")
        await stream.aclose()
        await self.assert_released(exchange)

    async def test_rejected_streams_release_without_success(self):
        scenarios = {
            "empty": [], "premature": [event("BILLING").encode()],
            "error": [event(finish="ERROR").encode()],
            "malformed": [b"data: {broken\n\n"],
            "read_failure": [event("BILLING").encode(), httpx.ReadError("synthetic read failure")],
        }
        for name, fragments in scenarios.items():
            with self.subTest(name=name):
                exchange = self.exchange(fragments)
                stream = await exchange.async_stream()
                chunks = []
                try:
                    with self.assertRaises(MidStreamFallbackError):
                        async for chunk in stream:
                            chunks.append(chunk)
                finally:
                    await stream.aclose()
                self.assertFalse(any(c.choices[0].finish_reason == "stop" for c in chunks))
                await self.assert_released(exchange)

    async def test_constructor_failure_releases_acquired_response(self):
        exchange = self.exchange(complete())
        with patch(MODULE + ".OCIStreamWrapper", side_effect=RuntimeError("synthetic handoff")):
            with self.assertRaisesRegex(RuntimeError, "synthetic handoff"):
                await exchange.async_stream()
        await self.assert_released(exchange)

    async def test_non200_success_status_releases_rejected_response(self):
        exchange = self.exchange(complete(), status=201)
        with self.assertRaises(httpx.ResponseNotRead):
            await exchange.async_stream()
        await self.assert_released(exchange)

    async def test_close_failure_preserves_original_constructor_failure(self):
        exchange = self.exchange(complete())
        with patch(MODULE + ".OCIStreamWrapper", side_effect=RuntimeError("synthetic handoff")):
            with patch.object(httpx.Response, "aclose", side_effect=OSError("synthetic close")) as close:
                with self.assertRaisesRegex(RuntimeError, "synthetic handoff"):
                    await exchange.async_stream()
                close.assert_awaited_once()

    async def test_iterator_close_failure_still_releases_response(self):
        class BrokenIterator:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

            async def aclose(self):
                raise RuntimeError("synthetic iterator close")

        exchange = self.exchange(complete())
        with patch(MODULE + "._aiter_sse_events", return_value=BrokenIterator()):
            stream = await exchange.async_stream()
        await stream.aclose()
        await self.assert_released(exchange)

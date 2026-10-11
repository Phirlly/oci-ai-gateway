"""Synchronous OCI failure propagation, completion and stream ownership."""

import asyncio
import unittest

from litellm.exceptions import MidStreamFallbackError
from payload_fixture import event
from stream_fixture import text_then_finish, wrapper


class SyncStreamCorrection(unittest.TestCase):
    def assert_rejected(self, events):
        stream, source, log, notified = wrapper(events)
        emitted = []
        try:
            with self.assertRaises(MidStreamFallbackError) as caught:
                for chunk in stream:
                    emitted.append(chunk)
            self.assertEqual(caught.exception.status_code, 502)
            self.assertFalse(any(c.choices[0].finish_reason == "stop" for c in emitted))
            self.assertTrue(notified.wait(1), "native failure notification missing")
            log._restore_correlation_context.assert_called()
        finally:
            asyncio.run(stream.aclose())
        self.assertEqual(source.closed, 1)

    def test_error_finish_is_rejected(self):
        self.assert_rejected(text_then_finish("ERROR"))

    def test_cancelled_finish_is_rejected(self):
        self.assert_rejected(text_then_finish("USER_CANCEL"))

    def test_eof_without_finish_is_rejected(self):
        self.assert_rejected([event("BILLING").strip()])

    def test_empty_stream_is_rejected(self):
        self.assert_rejected([])

    def test_premature_done_cannot_be_hidden_by_later_complete(self):
        self.assert_rejected([event("BILLING").strip(), "data: [DONE]", event(finish="COMPLETE").strip()])

    def test_unknown_finish_is_rejected(self):
        self.assert_rejected(text_then_finish("unrecognized-reason"))

    def test_uppercase_stop_finishes_stream(self):
        stream, source, log, _ = wrapper(text_then_finish("STOP") + ["data: [DONE]"])
        try:
            chunks = list(stream)
            self.assertEqual("".join(c.choices[0].delta.content or "" for c in chunks), "BILLING")
            self.assertEqual([c.choices[0].finish_reason for c in chunks], [None, "stop"])
            log.failure_handler.assert_not_called()
        finally:
            asyncio.run(stream.aclose())
        self.assertEqual(source.closed, 1)

    def test_valid_finish_and_length_are_preserved(self):
        for reason, expected in (("COMPLETE", "stop"), ("MAX_TOKENS", "length")):
            with self.subTest(reason=reason):
                stream, source, log, _ = wrapper(text_then_finish(reason) + ["data: [DONE]"])
                try:
                    chunks = list(stream)
                    self.assertEqual([c.choices[0].finish_reason for c in chunks], [None, expected])
                    log.failure_handler.assert_not_called()
                finally:
                    asyncio.run(stream.aclose())
                self.assertEqual(source.closed, 1)

    def test_partial_consumption_closes_upstream(self):
        stream, source, _, _ = wrapper(text_then_finish("COMPLETE"))
        self.assertEqual(next(stream).choices[0].delta.content, "BILLING")
        asyncio.run(stream.aclose())
        self.assertEqual(source.closed, 1)

    def test_close_before_first_chunk_releases_upstream(self):
        stream, source, _, _ = wrapper(text_then_finish("COMPLETE"))
        asyncio.run(stream.aclose())
        asyncio.run(stream.aclose())
        self.assertEqual(source.closed, 1)

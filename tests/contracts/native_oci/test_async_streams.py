"""Asynchronous OCI failure propagation and cancellation cleanup."""

import asyncio
import unittest

from litellm.exceptions import MidStreamFallbackError
from payload_fixture import event
from stream_fixture import text_then_finish, wrapper


class AsyncStreamCorrection(unittest.IsolatedAsyncioTestCase):
    async def assert_rejected(self, events):
        stream, source, log, _ = wrapper(events, asynchronous=True)
        emitted = []
        try:
            with self.assertRaises(MidStreamFallbackError) as caught:
                async for chunk in stream:
                    emitted.append(chunk)
            self.assertEqual(caught.exception.status_code, 502)
            self.assertFalse(any(c.choices[0].finish_reason == "stop" for c in emitted))
            await asyncio.sleep(0)  # Let the adapter's scheduled failure callback run.
            log.dispatch_failure_handlers.assert_awaited_once()
            log._restore_correlation_context.assert_called()
        finally:
            await stream.aclose()
        self.assertEqual(source.closed, 1)

    async def test_error_finish_is_rejected(self):
        await self.assert_rejected(text_then_finish("ERROR"))

    async def test_cancelled_finish_is_rejected(self):
        await self.assert_rejected(text_then_finish("USER_CANCEL"))

    async def test_eof_without_finish_is_rejected(self):
        await self.assert_rejected([event("BILLING").strip()])

    async def test_empty_stream_is_rejected(self):
        await self.assert_rejected([])

    async def test_premature_done_cannot_be_hidden_by_later_complete(self):
        await self.assert_rejected([event("BILLING").strip(), "data: [DONE]", event(finish="COMPLETE").strip()])

    async def test_unknown_finish_is_rejected(self):
        await self.assert_rejected(text_then_finish("unrecognized-reason"))

    async def test_uppercase_stop_finishes_stream(self):
        stream, source, log, _ = wrapper(text_then_finish("STOP") + ["data: [DONE]"], asynchronous=True)
        try:
            chunks = [chunk async for chunk in stream]
            self.assertEqual("".join(c.choices[0].delta.content or "" for c in chunks), "BILLING")
            self.assertEqual([c.choices[0].finish_reason for c in chunks], [None, "stop"])
            await asyncio.sleep(0)
            log.dispatch_failure_handlers.assert_not_awaited()
        finally:
            await stream.aclose()
        self.assertEqual(source.closed, 1)

    async def test_valid_finish_and_length_are_preserved(self):
        for reason, expected in (("COMPLETE", "stop"), ("MAX_TOKENS", "length")):
            with self.subTest(reason=reason):
                stream, source, log, _ = wrapper(text_then_finish(reason) + ["data: [DONE]"], asynchronous=True)
                try:
                    chunks = [chunk async for chunk in stream]
                    self.assertEqual([c.choices[0].finish_reason for c in chunks], [None, expected])
                    await asyncio.sleep(0)
                    log.dispatch_failure_handlers.assert_not_awaited()
                finally:
                    await stream.aclose()
                self.assertEqual(source.closed, 1)

    async def test_partial_consumption_closes_upstream(self):
        stream, source, _, _ = wrapper(text_then_finish("COMPLETE"), asynchronous=True)
        self.assertEqual((await anext(stream)).choices[0].delta.content, "BILLING")
        await stream.aclose()
        self.assertEqual(source.closed, 1)

    async def test_close_before_first_chunk_releases_upstream(self):
        stream, source, _, _ = wrapper(text_then_finish("COMPLETE"), asynchronous=True)
        await stream.aclose()
        await stream.aclose()
        self.assertEqual(source.closed, 1)

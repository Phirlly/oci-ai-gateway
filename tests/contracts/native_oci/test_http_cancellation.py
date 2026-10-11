"""Active cancellation must propagate while shielded response cleanup completes."""

import asyncio
import unittest
from unittest.mock import patch

import anyio
import httpx

from payload_fixture import event
from http_fixture import AsyncBody, Exchange


class ActiveCancellation(unittest.IsolatedAsyncioTestCase):
    def exchange(self):
        body = AsyncBody([event("BILLING").encode()], block=True)
        exchange = Exchange(body, asynchronous=True)
        self.addAsyncCleanup(exchange.aclose)
        return exchange

    async def consume(self, stream, chunks, cancelled):
        try:
            async for chunk in stream:
                chunks.append(chunk)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        finally:
            await stream.aclose()

    def assert_cancelled_cleanup(self, exchange, chunks, cancelled):
        self.assertTrue(cancelled.is_set())
        self.assertEqual(exchange.body.close_started, 1)
        self.assertEqual(exchange.body.close_completed, 1)
        self.assertEqual([c.choices[0].delta.content for c in chunks], ["BILLING"])
        self.assertFalse(any(c.choices[0].finish_reason for c in chunks))
        self.assertFalse(exchange.handler.client.is_closed)

    async def test_task_cancellation_during_read_closes_transport(self):
        exchange = self.exchange()
        stream = await exchange.async_stream()
        chunks, cancelled = [], asyncio.Event()
        task = asyncio.create_task(self.consume(stream, chunks, cancelled))
        try:
            await asyncio.wait_for(exchange.body.read_blocked.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self.assert_cancelled_cleanup(exchange, chunks, cancelled)

    async def test_anyio_scope_cancellation_allows_close_checkpoint(self):
        exchange = self.exchange()
        stream = await exchange.async_stream()
        chunks, cancelled = [], asyncio.Event()
        with anyio.fail_after(3):
            async with anyio.create_task_group() as group:
                group.start_soon(self.consume, stream, chunks, cancelled)
                await exchange.body.read_blocked.wait()
                group.cancel_scope.cancel()
        self.assert_cancelled_cleanup(exchange, chunks, cancelled)

    async def test_cancelled_factory_handoff_shields_response_close(self):
        exchange = self.exchange()
        with anyio.CancelScope() as scope:
            def cancelled_constructor(*args, **kwargs):
                scope.cancel()
                raise asyncio.CancelledError
            with patch("litellm.llms.oci.chat.transformation.OCIStreamWrapper",
                       side_effect=cancelled_constructor):
                with self.assertRaises(asyncio.CancelledError):
                    await exchange.async_stream()
        self.assertEqual(exchange.body.close_started, 1)
        self.assertEqual(exchange.body.close_completed, 1)

    async def test_close_failure_does_not_replace_factory_cancellation(self):
        exchange = self.exchange()
        with patch("litellm.llms.oci.chat.transformation.OCIStreamWrapper",
                   side_effect=asyncio.CancelledError):
            with patch.object(httpx.Response, "aclose", side_effect=OSError("synthetic close")) as close:
                with self.assertRaises(asyncio.CancelledError):
                    await exchange.async_stream()
                close.assert_awaited_once()

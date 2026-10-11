"""A cancelled signing wait cannot dispatch inference after the reply arrives."""

import asyncio
import gc
import warnings

from socket_signer_fixture import SocketProxyCase


class SocketProxyCancellation(SocketProxyCase):
    observe_signing_completion = True

    async def test_delayed_signing_keeps_proxy_responsive(self):
        self.socket.release.clear()
        task = asyncio.create_task(self.request())
        try:
            await self.wait_received()
            async with asyncio.timeout(0.5):
                response = await self.client.get("/health/liveliness")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(task.done())
            await self.release_signer()
            self.assertEqual((await task).status_code, 200)
        finally:
            self.socket.release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def assert_cancelled(self, streaming):
        self.socket.release.clear()
        loop, task_errors = asyncio.get_running_loop(), []
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda active_loop, context: task_errors.append(context.get("message")))
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter("always", RuntimeWarning)
            task = asyncio.create_task(self.request({"stream": streaming}))
            try:
                await self.wait_received()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 2)
                await self.release_signer()
                gc.collect()
                await asyncio.sleep(0.1)
                self.assertEqual(len(self.socket.requests), 1)
                self.assertEqual(self.upstream.requests, [])
                self.assertEqual([str(item.message) for item in observed
                                  if "was never awaited" in str(item.message)], [])
                self.assertEqual(task_errors, [])
            finally:
                loop.set_exception_handler(previous)
                self.socket.release.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_cancelled_completion_has_no_late_inference_or_abandoned_coroutine(self):
        await self.assert_cancelled(False)

    async def test_cancelled_stream_has_no_late_inference_or_abandoned_coroutine(self):
        await self.assert_cancelled(True)

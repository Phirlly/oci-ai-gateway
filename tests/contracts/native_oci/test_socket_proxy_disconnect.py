"""Exercise an actual ASGI disconnect event during the signing wait."""

import asyncio
import gc
import json
import warnings

from litellm.proxy import proxy_server
from payload_fixture import ROUTE
from native_proxy_fixture import MASTER
from socket_signer_fixture import SocketProxyCase


class SocketProxyDisconnect(SocketProxyCase):
    async def assert_disconnected(self, streaming):
        proxy_server.general_settings = {**proxy_server.general_settings, "cancel_on_disconnect": True}
        body = json.dumps({"model": ROUTE, "messages": [{"role": "user", "content": "Synthetic request"}],
                           "max_tokens": 32, "stream": streaming}).encode()
        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
                 "http_version": "1.1", "method": "POST", "scheme": "http", "root_path": "",
                 "path": "/chat/completions", "raw_path": b"/chat/completions", "query_string": b"",
                 "server": ("proxy.test", 80), "client": ("127.0.0.1", 1234),
                 "headers": [(b"authorization", ("Bearer " + MASTER).encode()),
                             (b"content-type", b"application/json"),
                             (b"content-length", str(len(body)).encode())]}
        sent, delivered = [], False

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            await self.wait_received()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        self.socket.release.clear()
        loop, task_errors = asyncio.get_running_loop(), []
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda active_loop, context: task_errors.append(context.get("message")))
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter("always", RuntimeWarning)
            try:
                await asyncio.wait_for(proxy_server.app(scope, receive, send), 3)
                self.assertTrue(self.socket.received.is_set())
                self.assertFalse(self.socket.completed.is_set())
                self.assertIn(499, [value.get("status") for value in sent])
                await self.release_signer()
                gc.collect()
                await asyncio.sleep(0.1)
                self.assertEqual(self.probe.upstream.requests, [])
                self.assertEqual([str(item.message) for item in observed
                                  if "was never awaited" in str(item.message)], [])
                self.assertEqual(task_errors, [])
            finally:
                loop.set_exception_handler(previous)
                self.socket.release.set()

    async def test_completion_disconnect_cancels_signing_wait_before_inference(self):
        await self.assert_disconnected(False)

    async def test_stream_disconnect_cancels_signing_wait_before_inference(self):
        await self.assert_disconnected(True)

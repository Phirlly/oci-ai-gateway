"""Finite loopback proof that early native stream closure releases a TCP peer."""

import asyncio
import unittest

import httpx
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
from litellm.llms.oci.chat.transformation import OCIChatConfig

from payload_fixture import MODEL, event
from http_fixture import logging_object


class NativeSocketClosure(unittest.IsolatedAsyncioTestCase):
    async def test_early_close_reaches_loopback_server(self):
        peer_closed = asyncio.Event()
        server_tasks = set()
        failures = []
        responses = []

        async def retain_response(response):
            responses.append(response)

        async def respond(reader, writer):
            task = asyncio.current_task()
            server_tasks.add(task)
            try:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2)
                length = next(int(line.split(b":", 1)[1]) for line in head.split(b"\r\n")
                              if line.lower().startswith(b"content-length:"))
                await asyncio.wait_for(reader.readexactly(length), 2)
                chunk = event("BILLING").encode()
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                             b"Transfer-Encoding: chunked\r\n\r\n"
                             + f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                await writer.drain()
                if await asyncio.wait_for(reader.read(1), 3) == b"":
                    peer_closed.set()
            except Exception as error:
                failures.append(type(error).__name__)
            finally:
                writer.close()
                await writer.wait_closed()
                server_tasks.discard(task)

        server = await asyncio.start_server(respond, "127.0.0.1", 0)
        handler = AsyncHTTPHandler(transport=httpx.AsyncHTTPTransport(retries=0), timeout=2,
                                   event_hooks={"response": [retain_response]})
        stream = None
        try:
            port = server.sockets[0].getsockname()[1]
            stream = await OCIChatConfig().get_async_custom_stream_wrapper(
                model=MODEL, custom_llm_provider="oci", logging_obj=logging_object(),
                api_base=f"http://127.0.0.1:{port}/chat", headers={}, data={},
                messages=[], client=handler,
            )
            chunk = await asyncio.wait_for(anext(stream), 2)
            self.assertEqual(chunk.choices[0].delta.content, "BILLING")
            await stream.aclose()
            self.assertTrue(responses[0].is_closed)
            await asyncio.wait_for(peer_closed.wait(), 2)
            self.assertFalse(handler.client.is_closed)
            self.assertEqual(failures, [])
        finally:
            if stream is not None:
                await stream.aclose()
            for response in responses:
                await response.aclose()
            await handler.close()
            server.close()
            await server.wait_closed()
            for task in tuple(server_tasks):
                task.cancel()
            await asyncio.gather(*server_tasks, return_exceptions=True)

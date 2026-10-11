"""Pinned proxy response/finalizer cleanup, without proxy authentication claims."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from starlette.requests import ClientDisconnect
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.common_request_processing import (
    ProxyBaseLLMRequestProcessing, _UpstreamClosingStreamingResponse,
)

from payload_fixture import event
from http_fixture import AsyncBody, Exchange


class ProxyStreamCleanup(unittest.IsolatedAsyncioTestCase):
    def exchange(self, fragments):
        exchange = Exchange(AsyncBody(fragments, block=True), asynchronous=True)
        self.addAsyncCleanup(exchange.aclose)
        return exchange

    def response(self, stream, request_data):
        log = MagicMock()
        log.async_post_call_streaming_iterator_hook.side_effect = lambda **kwargs: kwargs["response"]
        log._arelease_max_parallel_requests_on_disconnect = AsyncMock()
        body = ProxyBaseLLMRequestProcessing.async_streaming_data_generator(
            response=stream, user_api_key_dict=UserAPIKeyAuth(), request_data=request_data,
            proxy_logging_obj=log, serialize_chunk=lambda chunk: chunk.model_dump_json(),
            serialize_error=lambda error: str(error),
        )
        return _UpstreamClosingStreamingResponse(body, upstream_generator=stream)

    async def test_send_failure_before_iteration_closes_native_response(self):
        exchange = self.exchange([])
        stream = await exchange.async_stream()
        response = self.response(stream, {})

        async def send(message):
            raise OSError("synthetic downstream disconnect")

        with self.assertRaises(ClientDisconnect):
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, AsyncMock(), send)
        self.assertEqual(exchange.body.close_completed, 1)
        self.assertFalse(exchange.body.read_blocked.is_set())

    async def test_disconnect_during_read_runs_real_proxy_finalizer(self):
        exchange = self.exchange([event("BILLING").encode()])
        stream = await exchange.async_stream()
        request_data, sent = {}, []
        response = self.response(stream, request_data)

        async def receive():
            await exchange.body.read_blocked.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        await asyncio.wait_for(response(
            {"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send,
        ), 3)
        self.assertEqual(exchange.body.close_started, 1)
        self.assertEqual(exchange.body.close_completed, 1)
        self.assertTrue(any(b"BILLING" in message.get("body", b"") for message in sent))
        self.assertFalse(any(b'"finish_reason":"stop"' in message.get("body", b"") for message in sent))
        self.assertIs(request_data["metadata"]["client_disconnected"], True)
        self.assertEqual(request_data["metadata"]["error_information"]["error_code"], "499")

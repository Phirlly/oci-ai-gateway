"""Real HTTPX responses through the pinned native factories; synthetic transport."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import anyio
import httpx
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
from litellm.llms.oci.chat.transformation import OCIChatConfig

from payload_fixture import MODEL, event

URL = "https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com/20231130/actions/chat"


def logging_object():
    log = MagicMock()
    log.model_call_details = {"custom_llm_provider": "oci", "litellm_params": {}}
    log._llm_caching_handler = None
    log._on_deferred_stream_complete = None
    log.async_success_handler = AsyncMock()
    log.dispatch_success_handlers = AsyncMock()
    log.dispatch_failure_handlers = AsyncMock()
    return log


def complete(reason="COMPLETE"):
    return [event("BILLING").encode(), event(finish=reason).encode(), b"data: [DONE]\n\n"]


class SyncBody(httpx.SyncByteStream):
    def __init__(self, fragments):
        self.fragments = fragments
        self.close_started = 0
        self.close_completed = 0

    def __iter__(self):
        for fragment in self.fragments:
            if isinstance(fragment, Exception):
                raise fragment
            yield fragment

    def close(self):
        self.close_started += 1
        self.close_completed += 1


class AsyncBody(httpx.AsyncByteStream):
    def __init__(self, fragments, *, block=False):
        self.fragments = fragments
        self.block = block
        self.read_blocked = asyncio.Event()
        self.close_started = 0
        self.close_completed = 0

    async def __aiter__(self):
        for fragment in self.fragments:
            if isinstance(fragment, Exception):
                raise fragment
            yield fragment
        if self.block:
            self.read_blocked.set()
            await asyncio.Event().wait()

    async def aclose(self):
        self.close_started += 1
        await anyio.sleep(0)
        self.close_completed += 1


class Exchange:
    def __init__(self, body, *, asynchronous=False, status=200):
        self.body = body
        self.status = status
        self.responses = []
        self.requests = []
        transport = httpx.MockTransport(self.reply)
        if asynchronous:
            self.handler = AsyncHTTPHandler(transport=transport, timeout=2)
        else:
            self.handler = HTTPHandler(client=httpx.Client(transport=transport, timeout=2))
        self.log = logging_object()

    def reply(self, request):
        self.requests.append(request)
        if request.url.path == "/again":
            return httpx.Response(200, content=b"alive")
        response = httpx.Response(self.status, stream=self.body,
                                  headers={"content-type": "text/event-stream"})
        self.responses.append(response)
        return response

    def arguments(self):
        return dict(model=MODEL, custom_llm_provider="oci", logging_obj=self.log,
                    api_base=URL, headers={}, data={}, messages=[], client=self.handler)

    def sync_stream(self):
        return OCIChatConfig().get_sync_custom_stream_wrapper(**self.arguments())

    async def async_stream(self):
        return await OCIChatConfig().get_async_custom_stream_wrapper(**self.arguments())

    def close(self):
        for response in self.responses:
            response.close()
        self.handler.client.close()

    async def aclose(self):
        for response in self.responses:
            await response.aclose()
        await self.handler.client.aclose()

"""Synthetic native service behind a real HTTPX transport."""

import json

import httpx
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler

from payload_fixture import response_body
from http_fixture import AsyncBody, complete


class NativeUpstream:
    def __init__(self):
        self.requests = []
        self.bodies = []
        self.mode = "complete"
        self.handler = AsyncHTTPHandler(transport=httpx.MockTransport(self.reply),
                                       follow_redirects=False, timeout=3)

    def reply(self, request):
        self.requests.append(request)
        if self.mode == "rate_limit":
            return httpx.Response(429, json={"code": "TooManyRequests", "message": "Synthetic limit"},
                                  headers={"retry-after": "7"})
        data = json.loads(request.content)
        reason = "ERROR" if self.mode == "error" else "COMPLETE"
        if data["chatRequest"].get("isStream"):
            fragments = complete(reason)
            if self.mode == "premature":
                fragments = fragments[:1]
            body = AsyncBody(fragments)
            self.bodies.append(body)
            return httpx.Response(200, stream=body, headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json=response_body(reason))

    async def close(self):
        await self.handler.close()

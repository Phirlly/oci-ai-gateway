"""Synthetic native service behind a real HTTPX transport."""

import json

import httpx
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler

from payload_fixture import response_body
from http_fixture import AsyncBody, complete
from external_payload_fixture import external_response


class NativeUpstream:
    def __init__(self):
        self.requests = []
        self.bodies = []
        self.mode = "complete"
        self.handler = AsyncHTTPHandler(transport=httpx.MockTransport(self.reply),
                                       follow_redirects=False, timeout=3)

    def reply(self, request):
        self.requests.append(request)
        if request.url.host == "api.anthropic.com":
            if self.mode == "context_error":
                return httpx.Response(400, json={"type": "error", "error": {
                    "type": "invalid_request_error", "message": "prompt is too long"}})
            value = external_response(json.loads(request.content).get("stream", False))
            if isinstance(value, dict):
                return httpx.Response(200, json=value)
            body = AsyncBody([("event: " + item["type"] + "\ndata: " + json.dumps(item)
                               + "\n\n").encode() for item in value])
            self.bodies.append(body)
            return httpx.Response(200, stream=body, headers={"content-type": "text/event-stream"})
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

"""Caller streaming timeouts are rejected; operator configuration still applies."""

from litellm.proxy import proxy_server

from admission_fixture import AdmissionCase
from demo.results import streamed_completion
from native_proxy_fixture import EXTERNAL
from payload_fixture import USAGE


class GatewayTimeouts(AdmissionCase):
    async def test_body_stream_timeout_is_denied_before_signing_or_provider_calls(self):
        await self.deny({"stream": True, "stream_timeout": 600})

    async def test_header_stream_timeout_is_denied_before_signing_or_provider_calls(self):
        await self.deny({"stream": True}, headers={"x-litellm-stream-timeout": "600"})

    async def test_external_stream_keeps_operator_timeout_and_usage(self):
        # Distinct from the synthetic HTTP client's default3; set server policy.
        proxy_server.llm_router.stream_timeout = 7
        response = await self.request({"model": EXTERNAL, "stream": True,
                                       "stream_options": {"include_usage": True}})
        self.assertEqual(response.status_code, 200, response.text[:200])
        self.assertEqual(streamed_completion(self.result(response), EXTERNAL), ("BILLING", USAGE))
        self.assertEqual(len(self.upstream.requests), 1)
        self.assertEqual(self.upstream.requests[0].extensions["timeout"]["read"], 7)
        self.assertEqual(self.socket.requests, [])

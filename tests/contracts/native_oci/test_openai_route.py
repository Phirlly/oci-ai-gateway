"""Actual pinned proxy/OpenAI adapter, with only outbound HTTP replaced."""

import json

from demo.results import completion, streamed_completion
from native_proxy_fixture import NativeProxyCase
from openai_payload_fixture import MODEL, USAGE

ALIAS = "external-openai"


class OpenAIOnlyRoute(NativeProxyCase):
    providers = ("openai",)

    async def test_completion_and_stream_have_expected_auth_model_and_usage(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                before = len(self.upstream.requests)
                response = await self.request({"model": ALIAS, "stream": stream,
                                               **({"stream_options": {"include_usage": True}} if stream else {})})
                self.assertEqual(response.status_code, 200, response.text[:200])
                parse = streamed_completion if stream else completion
                self.assertEqual(parse(self.result(response), ALIAS), ("BILLING", USAGE))
                self.assertEqual(len(self.upstream.requests), before + 1)
                request = self.upstream.requests[-1]
                self.assertEqual(str(request.url), "https://api.openai.com/v1/chat/completions")
                self.assertEqual(request.headers["authorization"], "Bearer synthetic-openai-key")
                self.assertEqual(json.loads(request.content)["model"], MODEL)

    async def test_disabled_provider_cannot_reach_transport(self):
        for model in ("oci-managed", "external-anthropic"):
            response = await self.request({"model": model})
            self.assertIn(response.status_code, (400, 404))
        self.assertEqual(self.upstream.requests, [])

    async def test_provider_429_is_not_retried_by_the_adapter(self):
        self.upstream.mode = "rate_limit"
        response = await self.request({"model": ALIAS})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(self.upstream.requests), 1)


class OpenAIAlongsideProviders(OpenAIOnlyRoute):
    providers = ("oci", "anthropic", "openai")

    async def test_disabled_provider_cannot_reach_transport(self):
        # Here all three are enabled: reject a fourth route before transport.
        response = await self.request({"model": "unconfigured"})
        self.assertIn(response.status_code, (400, 404))
        self.assertEqual(self.upstream.requests, [])

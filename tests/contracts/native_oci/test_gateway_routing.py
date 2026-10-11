"""Both configured adapters run; only native OCI receives signing authority."""

import json

from demo.results import completion, streamed_completion
from http_fixture import URL
from native_proxy_fixture import EXTERNAL
from payload_fixture import COMPARTMENT, MODEL, ROUTE, USAGE
from socket_signer_fixture import SIGNATURE_MARKER, SocketProxyCase


class GatewayRouting(SocketProxyCase):
    async def test_native_empty_terminal_event_preserves_complete_stream_and_unknown_usage(self):
        self.upstream.mode = "empty_tail"
        response = await self.request({"stream": True, "stream_options": {"include_usage": True}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(streamed_completion(self.result(response), ROUTE), ("BILLING", None))
        self.assertEqual(len(self.socket.requests), 1)
        self.assertEqual(len(self.upstream.requests), 1)

    async def test_native_completion_and_compare_stream_use_exact_signed_bytes(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                before = len(self.socket.requests)
                response = await self.request({"stream": streaming, "stream_options": {"include_usage": True}})
                self.assertEqual(response.status_code, 200, response.text[:200])
                parser = streamed_completion if streaming else completion
                self.assertEqual(parser(self.result(response), ROUTE), ("BILLING", None if streaming else USAGE))
                request = self.upstream.requests[-1]
                self.assertEqual(str(request.url), URL)
                self.assertEqual(request.method, "POST")
                self.assertIn(SIGNATURE_MARKER, request.headers["authorization"])
                self.assertEqual(request.content, self.socket.requests[-1])
                self.assertEqual(len(self.socket.requests), before + 1)
                body = json.loads(request.content)
                self.assertEqual(body["compartmentId"], COMPARTMENT)
                self.assertEqual(body["servingMode"], {"servingType": "ON_DEMAND", "modelId": MODEL})
                self.assertEqual(body["chatRequest"]["maxTokens"], 32)

    async def test_external_completion_and_stream_preserve_usage_without_signing(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                response = await self.request({"model": EXTERNAL, "stream": streaming,
                                               "stream_options": {"include_usage": True}})
                self.assertEqual(response.status_code, 200, response.text[:200])
                parser = streamed_completion if streaming else completion
                self.assertEqual(parser(self.result(response), EXTERNAL), ("BILLING", USAGE))
                request = self.upstream.requests[-1]
                self.assertEqual(str(request.url), "https://api.anthropic.com/v1/messages")
                self.assertEqual(request.headers["x-api-key"], "synthetic-external-key")
                self.assertNotIn("authorization", request.headers)
                self.assertEqual(self.socket.requests, [])

    async def test_other_unsupported_options_are_not_silently_dropped(self):
        response = await self.request({"top_logprobs": 2})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.socket.requests, [])
        self.assertEqual(self.upstream.requests, [])

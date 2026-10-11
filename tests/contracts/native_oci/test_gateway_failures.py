"""Provider failures cannot pass sample verification or add implicit retries."""

from demo.results import completion, streamed_completion
from payload_fixture import ROUTE
from runtime.gateway_http import GatewayError
from socket_signer_fixture import SocketProxyCase


class GatewayFailures(SocketProxyCase):
    async def test_native_error_completion_is_rejected(self):
        self.upstream.mode = "error"
        response = await self.request()
        self.assertNotEqual(response.status_code, 200)
        with self.assertRaises(GatewayError):
            completion(self.result(response), ROUTE)
        self.assertEqual(len(self.upstream.requests), 1)

    async def test_error_and_incomplete_streams_cannot_pass_samples(self):
        for mode in ("error", "premature"):
            with self.subTest(mode=mode):
                before = len(self.upstream.requests)
                self.upstream.mode = mode
                response = await self.request({"stream": True})
                with self.assertRaises(GatewayError):
                    streamed_completion(self.result(response), ROUTE)
                self.assertEqual(len(self.upstream.requests), before + 1)
                self.assertEqual(self.upstream.bodies[-1].close_completed, 1)

    async def test_429_has_exactly_one_signing_and_provider_attempt(self):
        self.upstream.mode = "rate_limit"
        response = await self.request()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(self.socket.requests), 1)
        self.assertEqual(len(self.upstream.requests), 1)

"""External-only admission uses the real callback without creating an OCI signer."""

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from runtime.oci_gateway_callback import NativeGateway
from runtime.oci_gateway_config import GatewayRoutes


class OptionalAdmission(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.signer = self.enterContext(patch("runtime.oci_gateway_callback.SocketSigner"))
        self.callback = NativeGateway(GatewayRoutes(None, None, "openai/gpt-4.1-mini-2025-04-14"))

    async def test_openai_route_never_creates_or_attaches_native_signer(self):
        self.signer.assert_not_called()
        body = {"model": "external-openai", "messages": [{"role": "user", "content": "synthetic"}]}
        data = dict(body, proxy_server_request={"body": body})
        self.assertIs(await self.callback.async_pre_call_hook(None, None, data, "acompletion"), data)
        params = {"model": self.callback.routes.openai_model, "custom_llm_provider": "openai"}
        self.assertIs(await self.callback.async_pre_call_deployment_hook(params, "acompletion"), params)
        self.assertNotIn("oci_signer", params)

    async def test_disabled_alias_and_request_override_are_denied(self):
        for body in ({"model": "oci-managed"}, {"model": "external-anthropic"},
                     {"model": "external-openai", "api_base": "https://example.invalid"}):
            with self.subTest(body=body), self.assertRaises(HTTPException):
                await self.callback.async_pre_call_hook(None, None, dict(body, proxy_server_request={"body": body}), "acompletion")

    async def test_provider_or_native_scope_injection_is_denied_before_transport(self):
        for change in ({"custom_llm_provider": "anthropic"}, {"model": "oci/other"},
                       {"oci_signer": "synthetic"}, {"api_base": "https://example.invalid"}):
            params = {"model": self.callback.routes.openai_model, **change}
            with self.subTest(change=change), self.assertRaises(HTTPException):
                await self.callback.async_pre_call_deployment_hook(params, "acompletion")

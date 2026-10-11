"""Production entrypoint, config-relative callback and authentication are active."""

import os
import unittest

from tests.contracts.runtime.gateway_client import GatewayClient


class NativeStartupContracts(unittest.TestCase):
    def test_configured_routes_are_available_after_database_startup(self):
        client = GatewayClient(os.environ["GATEWAY_TEST_MASTER_KEY"])
        health = client.request("GET", "/health/readiness")
        self.assertEqual(health.status, 200)
        self.assertEqual(health.json()["db"], "connected")
        models = client.request("GET", "/v1/models")
        self.assertEqual(models.status, 200)
        self.assertEqual({row["id"] for row in models.json()["data"]}, {"oci-managed", "external-anthropic"})

    def test_loaded_production_callback_denies_scope_override(self):
        client = GatewayClient(os.environ["GATEWAY_TEST_MASTER_KEY"])
        response = client.request("POST", "/chat/completions", {
            "model": "oci-managed", "messages": [{"role": "user", "content": "synthetic"}],
            "oci_region": "us-chicago-1"})
        self.assertEqual(response.status, 400)
        self.assertIn(b"Gateway route overrides are not permitted", response.body)

    def test_missing_auth_cannot_access_models(self):
        self.assertIn(GatewayClient().request("GET", "/v1/models").status, (401, 403))

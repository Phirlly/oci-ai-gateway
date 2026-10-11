"""Actual entrypoint, private files and callback work without OCI signing assets."""

import os
import unittest

from tests.contracts.runtime.gateway_client import GatewayClient


class ExternalStartupContracts(unittest.TestCase):
    def test_only_enabled_model_is_visible_after_database_startup(self):
        client = GatewayClient(os.environ["GATEWAY_TEST_MASTER_KEY"])
        health = client.request("GET", "/health/readiness")
        self.assertEqual(health.status, 200)
        self.assertEqual(health.json()["db"], "connected")
        models = client.request("GET", "/v1/models")
        self.assertEqual(models.status, 200)
        self.assertEqual([row["id"] for row in models.json()["data"]], ["external-openai"])

    def test_loaded_callback_denies_external_route_override(self):
        client = GatewayClient(os.environ["GATEWAY_TEST_MASTER_KEY"])
        response = client.request("POST", "/chat/completions", {
            "model": "external-openai", "messages": [{"role": "user", "content": "synthetic"}],
            "oci_region": "us-chicago-1"})
        self.assertEqual(response.status, 400)
        self.assertIn(b"Gateway route overrides are not permitted", response.body)

    def test_missing_auth_cannot_access_models(self):
        self.assertIn(GatewayClient().request("GET", "/v1/models").status, (401, 403))

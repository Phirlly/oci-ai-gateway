"""Startup authority is limited to the configured subset, including external-only."""

import unittest

from runtime.gateway_http import GatewayError
from runtime.oci_gateway_config import parse_routes
from runtime.provider_selection import model_aliases, model_routes
from .optional_fixture import SUBSETS, settings


class OptionalGatewayRoutesTests(unittest.TestCase):
    def test_each_subset_derives_only_its_authorized_targets(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers):
                config = settings(providers)
                routes = parse_routes({"model_list": model_routes(config)})
                self.assertEqual(routes.aliases, model_aliases(config))
                self.assertEqual(routes.scope is not None, "oci" in providers)
                self.assertEqual(routes.openai_model is not None, "openai" in providers)
                self.assertEqual(routes.external_model is not None, "anthropic" in providers)

    def test_openai_alias_cannot_route_to_another_provider_or_custom_endpoint(self):
        for change in ({"model": "anthropic/claude-sonnet-4-6"}, {"api_base": "https://example.invalid"},
                       {"api_key": "os.environ/ANTHROPIC_API_KEY"}):
            rows = model_routes(settings(("openai",)))
            rows[0]["litellm_params"].update(change)
            with self.subTest(change=change), self.assertRaises(GatewayError):
                parse_routes({"model_list": rows})

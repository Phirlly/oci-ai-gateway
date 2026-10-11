"""Startup authority comes from exactly two server-configured routes."""

import copy
import unittest
from dataclasses import FrozenInstanceError

from runtime.gateway_http import GatewayError
from runtime.oci_gateway_config import parse_routes
from .native_config_fixture import gateway_config


class NativeGatewayRoutes(unittest.TestCase):
    def test_scope_and_external_model_come_from_configuration_once(self):
        config = gateway_config()
        routes = parse_routes(config)
        self.assertEqual(routes.scope.region, "us-ashburn-1")
        self.assertEqual(routes.scope.compartment_id, "ocid1.compartment.oc1..synthetic")
        self.assertEqual(routes.scope.model_id, "google.gemini-2.5-flash-lite")
        self.assertEqual(routes.external_model, "anthropic/claude-sonnet-4-6")
        config["model_list"][0]["litellm_params"]["oci_region"] = "us-chicago-1"
        self.assertEqual(routes.scope.region, "us-ashburn-1")
        with self.assertRaises(FrozenInstanceError):
            routes.external_model = "changed"

    def test_missing_duplicate_and_extra_routes_are_rejected(self):
        rows = gateway_config()["model_list"]
        for value in (None, [], {}, {"model_list": []},
                      {"model_list": [rows[0], rows[0]]}, {"model_list": rows + [rows[0]]},
                      {"model_list": [None, rows[1]]}):
            with self.subTest(value=value), self.assertRaises(GatewayError):
                parse_routes(value)

    def test_invalid_scope_and_native_transport_options_fail_closed(self):
        changes = {"model": "openai/private-marker", "oci_region": "bad/region",
                   "oci_compartment_id": "invalid", "api_base": "https://private-marker",
                   "api_key": "private-marker", "oci_signer": {}, "client": {},
                   "max_tokens": 4097, "num_retries": 1,
                   "additional_drop_params": ["top_logprobs"]}
        for name, value in changes.items():
            with self.subTest(name=name):
                config = gateway_config()
                config["model_list"][0]["litellm_params"][name] = value
                with self.assertRaisesRegex(GatewayError, "^Native gateway configuration is invalid$"):
                    parse_routes(config)

    def test_external_route_requires_named_provider_and_environment_key(self):
        for changes in ({"model": "openai/private-marker"}, {"api_key": "private-marker"},
                        {"api_base": "https://private-marker"}, {"oci_region": "us-ashburn-1"}):
            with self.subTest(changes=changes):
                config = gateway_config()
                config["model_list"][1]["litellm_params"].update(changes)
                with self.assertRaises(GatewayError):
                    parse_routes(config)

    def test_valid_other_scope_and_order_do_not_depend_on_author_configuration(self):
        config = copy.deepcopy(gateway_config())
        config["model_list"].reverse()
        native = config["model_list"][1]["litellm_params"]
        native.update(oci_region="us-chicago-1", oci_compartment_id="ocid1.compartment.oc1..other",
                      model="oci/another-model")
        self.assertEqual(parse_routes(config).scope.region, "us-chicago-1")
        self.assertEqual(parse_routes(config).scope.model_id, "another-model")

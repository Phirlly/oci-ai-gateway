"""Canonical schema4 inputs select providers once and preserve original schemas."""

import json
import unittest

from deployment.credential_errors import DeliveryError
from deployment.deployment_config import load_config
from deployment.gateway_config import GatewayConfig
from tests.unit.runtime.optional_fixture import SUBSETS
from .optional_fixture import settings


class OptionalSettingsTests(unittest.TestCase):
    def test_every_subset_roundtrips_through_string_orm_variables(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers):
                config = load_config(json.dumps(settings(providers)))
                self.assertTrue(config.is_native)
                self.assertTrue(config.is_optional)
                variables = config.orm_variables(model_key_ocid=None)
                self.assertEqual(json.loads(variables["models"]), settings(providers)["models"])
                self.assertIsNone(config.read_binding(variables))
                self.assertNotIn("oci_model_id", variables)
                self.assertNotIn("external_provider", variables)
                self.assertEqual("inference_region" in variables, "oci" in providers)

    def test_original_or_returned_nested_input_cannot_mutate_config(self):
        value = settings()
        config = GatewayConfig(value)
        expected = config.orm_variables(model_key_ocid=None)
        value["models"]["openai"] = "changed"
        config.values["models"]["openai"] = "changed-again"
        self.assertEqual(config.orm_variables(model_key_ocid=None), expected)

    def test_mixed_or_missing_scope_rejected(self):
        missing = settings()
        del missing["inference_region"]
        for value in (settings() | {"models": {}}, missing,
                      settings(("openai",)) | {"inference_region": "us-ashburn-1"},
                      settings() | {"external_provider": "anthropic"},
                      settings() | {"model_key_ttl_days": 7}):
            with self.subTest(value=value), self.assertRaises(DeliveryError):
                load_config(json.dumps(value))

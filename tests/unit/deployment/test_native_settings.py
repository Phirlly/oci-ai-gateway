"""Native settings eliminate unused key lifecycle inputs and reject mixed versions."""

import json
import unittest

from deployment.credential_errors import DeliveryError
from deployment.deployment_config import load_config
from .gateway_config_fixture import GATEWAY_SETTINGS
from .native_fixture import NATIVE_SETTINGS
from .orm_fixtures import KEY_ID


class NativeSettingsTests(unittest.TestCase):
    def test_native_roundtrip_has_no_key_or_expiry_input(self):
        config = load_config(json.dumps(NATIVE_SETTINGS))
        self.assertTrue(config.is_native)
        variables = config.orm_variables(model_key_ocid=None)
        self.assertEqual(variables["schema_version"], "3")
        self.assertNotIn("model_key_ttl_days", variables)
        self.assertNotIn("oci_model_key_ocid", variables)
        self.assertIsNone(config.read_binding(variables))
        with self.assertRaises(DeliveryError):
            config.orm_variables(model_key_ocid=KEY_ID)

    def test_legacy_version_keeps_its_original_inputs_and_binding(self):
        config = load_config(json.dumps(GATEWAY_SETTINGS))
        self.assertFalse(config.is_native)
        self.assertEqual(config.read_binding(config.orm_variables(model_key_ocid=KEY_ID)), KEY_ID)

    def test_mixed_schema_fields_fail(self):
        for values in ({**NATIVE_SETTINGS, "model_key_ttl_days": 7},
                       {**NATIVE_SETTINGS, "schema_version": 2},
                       {**NATIVE_SETTINGS, "schema_version": True}):
            with self.subTest(version=values["schema_version"]), self.assertRaises(DeliveryError):
                load_config(json.dumps(values))

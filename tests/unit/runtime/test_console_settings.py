"""Direct deployment binds settings and verification runs to one instance."""

import json
import unittest

from runtime.console_settings import load_context, validate_console_settings
from runtime.gateway_http import GatewayError
from .console_fixture import context, settings


class ConsoleSettingsTests(unittest.TestCase):
    def test_context_accepts_exact_settings_and_public_identity(self):
        value = context()
        self.assertEqual(load_context(json.dumps(value).encode(), settings(), value["instance_ocid"]), value)
        self.assertEqual(validate_console_settings(settings()), settings())

    def test_rejects_wrong_identity_private_address_and_unbounded_runs(self):
        changes = {"verification_run": [0, 21, True, 1.5], "public_ip": ["127.0.0.1", "::1"],
                   "instance_ocid": ["ocid1.instance.oc1.iad.other"]}
        for field, values in changes.items():
            for value in values:
                changed = context()
                changed[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(GatewayError):
                    load_context(json.dumps(changed).encode(), settings(), context()["instance_ocid"])
        changed = context()
        changed["settings"]["native"]["model_id"] = "different-model"
        with self.assertRaises(GatewayError):
            load_context(json.dumps(changed).encode(), settings(), context()["instance_ocid"])

    def test_rejects_duplicate_fields_and_unknown_settings(self):
        with self.assertRaises(GatewayError):
            load_context(b'{"schema_version":1,"schema_version":1}', settings(), context()["instance_ocid"])
        value = settings()
        value["secret_value"] = "not-allowed"
        with self.assertRaises(GatewayError):
            validate_console_settings(value)

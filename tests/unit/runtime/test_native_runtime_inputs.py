"""Native runtime wire validation and file rendering share one signing scope."""

import json
import tempfile
import unittest
from pathlib import Path

from runtime.gateway_entrypoint import entry_environment
from runtime.gateway_http import GatewayError
from runtime.oci_gateway_config import parse_routes
from runtime.runtime_bundle import load_bundle
from runtime.runtime_files import runtime_files
from .bundle_fixture import INSTANCE, NOW, SETTINGS, bundle
from .native_bundle_fixture import NATIVE_SETTINGS, native_bundle


class NativeRuntimeInputTests(unittest.TestCase):
    def load(self, value=None, settings=None):
        return load_bundle(json.dumps(value or native_bundle()).encode(),
                           settings or NATIVE_SETTINGS, INSTANCE, now=NOW)

    def test_native_settings_require_native_bundle_and_reject_legacy_fields(self):
        self.assertNotIn("oci_api_key", self.load().credentials)
        for value, settings in ((bundle(), NATIVE_SETTINGS), (native_bundle(), SETTINGS),
                                (native_bundle() | {"expires_at": "2040-01-01T00:00:00Z"}, NATIVE_SETTINGS)):
            with self.subTest(version=value["schema_version"]), self.assertRaises(GatewayError):
                self.load(value, settings)

    def test_rendered_config_loads_exact_native_scope_and_production_callback(self):
        files = runtime_files(self.load())
        config = json.loads(files["gateway.json"])
        routes = parse_routes(config)
        self.assertEqual(routes.scope.model_id, NATIVE_SETTINGS["model_id"])
        self.assertEqual(routes.scope.compartment_id, NATIVE_SETTINGS["compartment_ocid"])
        self.assertEqual(config["litellm_settings"]["callbacks"], ["runtime.oci_gateway_loader.INSTANCE"])
        self.assertEqual(config["model_list"][0]["litellm_params"]["max_tokens"], 256)
        self.assertNotIn("api_base", files["gateway.json"])
        self.assertNotIn("oci_api_key", files["gateway-secrets.json"])
        self.assertNotIn("demo_password", files["gateway-secrets.json"])

    def test_native_entrypoint_does_not_export_oci_bearer_credentials(self):
        files = runtime_files(self.load())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gateway.json"
            path.write_text(files["gateway-secrets.json"])
            path.chmod(0o600)
            environment = entry_environment(path)
        self.assertEqual(set(environment), {"DATABASE_URL", "LITELLM_MASTER_KEY", "LITELLM_SALT_KEY", "ANTHROPIC_API_KEY"})

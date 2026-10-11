"""The systemd worker resolves the OCI scope from the validated schema4 settings."""

import io
import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from runtime import oci_signing_entrypoint as entrypoint
from runtime.runtime_bundle import validate_settings
from .optional_fixture import settings


class OptionalSigningEntrypointTests(unittest.TestCase):
    def invoke(self, value):
        signer = Mock()
        serve = Mock(return_value=0)
        with patch.object(entrypoint.os, "geteuid", return_value=0), \
                patch.object(entrypoint.signal, "signal"), \
                patch.object(entrypoint, "load_settings", return_value=validate_settings(value)), \
                patch.object(entrypoint, "InstanceSigner", signer), \
                patch.object(entrypoint, "activated_listener", return_value=nullcontext("listener")), \
                patch.object(entrypoint, "serve", serve), patch("sys.stderr", io.StringIO()):
            result = entrypoint.main()
        return result, signer, serve

    def test_oci_enabled_settings_start_the_scoped_worker(self):
        value = settings(("oci", "openai"))
        result, signer, serve = self.invoke(value)
        self.assertEqual(result, 0)
        scope, tenancy, region = signer.call_args.args
        self.assertEqual(scope.model_id, value["models"]["oci"])
        self.assertEqual(scope.region, value["inference_region"])
        self.assertEqual(scope.compartment_id, value["compartment_ocid"])
        self.assertEqual((tenancy, region), (value["tenancy_ocid"], value["region"]))
        serve.assert_called_once_with("listener", signer.return_value)

    def test_external_only_settings_cannot_start_a_signer(self):
        result, signer, serve = self.invoke(settings(("openai",)))
        self.assertEqual(result, 1)
        signer.assert_not_called()
        serve.assert_not_called()

    def test_legacy_schema3_still_resolves_its_original_scope(self):
        value = settings(("oci",))
        value.update(schema_version=3, model_id=value.pop("models")["oci"],
                     external_provider="anthropic", external_model_id="claude-sonnet-4-6")
        result, signer, serve = self.invoke(value)
        self.assertEqual(result, 0)
        self.assertEqual(signer.call_args.args[0].model_id, value["model_id"])
        serve.assert_called_once()

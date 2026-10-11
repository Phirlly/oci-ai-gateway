"""The actual loader rejects invalid startup config and never reuses old scope."""

import json
from pathlib import Path

from litellm.proxy.types_utils.utils import get_instance_fn

from native_proxy_fixture import NativeProxyCase
from runtime.gateway_http import GatewayError


class GatewayLoading(NativeProxyCase):
    def load_again(self):
        return get_instance_fn("runtime.oci_gateway_loader.INSTANCE",
                               config_file_path=str(Path(self.directory.name) / "config.yaml"))

    async def test_new_import_reads_new_scope_while_existing_instance_stays_fixed(self):
        path = Path(self.directory.name) / "config.yaml"
        config = json.loads(path.read_text())
        config["model_list"][0]["litellm_params"]["oci_region"] = "us-chicago-1"
        path.write_text(json.dumps(config))
        other = self.load_again()
        self.assertIsNot(other, self.probe)
        self.assertEqual(other.routes.scope.region, "us-chicago-1")
        self.assertEqual(self.probe.routes.scope.region, "us-ashburn-1")
        self.assertEqual(other.oci_signer.scope, other.routes.scope)

    async def test_invalid_and_missing_startup_config_cannot_return_an_instance(self):
        path = Path(self.directory.name) / "config.yaml"
        path.write_text('{"model_list": []}')
        with self.assertRaisesRegex(GatewayError, "^Native gateway configuration is invalid$"):
            self.load_again()
        path.unlink()
        with self.assertRaises(GatewayError):
            self.load_again()
        self.assertEqual(self.upstream.requests, [])

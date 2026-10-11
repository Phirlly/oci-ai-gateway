"""Production native Compose mounts only the private socket and verified overlays."""

import json
import unittest

from runtime.oci_adapter_overlay import IMAGE, IMAGE_MODULE_ROOT
from .stack import ROOT, docker_command, run_command


class NativeConfigurationContracts(unittest.TestCase):
    def test_native_mounts_and_callback_module_path_are_explicit(self):
        config = json.loads(run_command(docker_command() + ["compose", "-f",
                            str(ROOT / "runtime/compose.native.yaml"), "config", "--format", "json"]))
        gateway = config["services"]["gateway"]
        self.assertEqual(gateway["image"], IMAGE)
        self.assertEqual(gateway["environment"]["PYTHONPATH"], "/app")
        mounts = {row["target"]: row for row in gateway["volumes"]}
        for target in ("/app/runtime", "/app/config.json", "/run/oci-ai-gateway-signing",
                       IMAGE_MODULE_ROOT + "/llms/oci/chat/generic.py",
                       IMAGE_MODULE_ROOT + "/llms/oci/chat/transformation.py"):
            self.assertTrue(mounts[target]["read_only"])
            self.assertFalse(mounts[target]["bind"].get("create_host_path", False))
        self.assertNotIn("/var/lib/oci-ai-gateway", mounts)
        self.assertFalse(any("docker.sock" in row["source"] for row in mounts.values()))
        self.assertEqual(gateway["ports"][0]["host_ip"], "127.0.0.1")

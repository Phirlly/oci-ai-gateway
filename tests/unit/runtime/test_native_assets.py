"""Native asset destinations are explicit and validated before installation."""

import json
import tempfile
import unittest
from pathlib import Path

from runtime.install_assets import install_assets


class NativeAssetTests(unittest.TestCase):
    def test_native_units_patch_and_license_install_to_fixed_paths(self):
        values = {"runtime/systemd/oci-ai-gateway-signing.socket": "socket unit",
                  "runtime/systemd/oci-ai-gateway-signing.service": "service unit",
                  "runtime/litellm_oci.patch": "patch", "runtime/LITELLM_LICENSE": "license"}
        content = json.dumps(values).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install_assets(content, root)
            self.assertEqual((root / "etc/systemd/system/oci-ai-gateway-signing.socket").read_text(), "socket unit")
            self.assertEqual((root / "opt/oci-ai-gateway/runtime/litellm_oci.patch").read_text(), "patch")

    def test_duplicate_destinations_are_rejected_before_writes(self):
        values = {"runtime/systemd/docker-native.conf": "native", "runtime/systemd/docker-guard.conf": "legacy"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                install_assets(json.dumps(values).encode(), root)
            self.assertFalse(list(root.iterdir()))

    def test_unknown_decoded_path_prevents_all_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = json.dumps({"runtime/bootstrap.py": "code", "../private": "bad"}).encode()
            with self.assertRaises(ValueError):
                install_assets(content, root)
            self.assertFalse(list(root.iterdir()))

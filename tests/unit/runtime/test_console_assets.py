"""Console bootstrap installs only the named sample assets, within fixed budgets."""

import json
import tempfile
import unittest
from pathlib import Path

from runtime.install_assets import asset_destination, install_assets
from runtime.source_archive import validate_manifest


class ConsoleAssetTests(unittest.TestCase):
    def test_sample_and_console_service_paths(self):
        for name in ("demo/verification.py", "demo/support-requests.json", "demo/expected-categories.json",
                     "runtime/compose.console.yaml"):
            self.assertEqual(asset_destination(name), "opt/oci-ai-gateway/" + name)
        self.assertEqual(asset_destination("runtime/systemd/oci-ai-gateway-console-bootstrap.service"),
                         "etc/systemd/system/oci-ai-gateway-bootstrap.service")

    def test_demo_allowlist_rejects_unrelated_or_nested_files(self):
        for name in ("demo/settings.json", "demo/credentials.py", "demo/../runtime/bootstrap.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                asset_destination(name)

    def test_manifest_and_installer_share_eighty_file_limit(self):
        values = {"runtime/asset_" + chr(97 + i // 26) + chr(97 + i % 26) + ".py": "# safe\n"
                  for i in range(81)}
        for count in (80, 81):
            subset = dict(list(values.items())[:count])
            manifest = {"schema_version": 1, "repository": "synthetic/gateway", "commit": "a" * 40,
                        "files": {name: "a" * 64 for name in subset}}
            with tempfile.TemporaryDirectory() as directory:
                if count == 80:
                    validate_manifest(manifest)
                    install_assets(json.dumps(subset).encode(), Path(directory))
                else:
                    with self.assertRaises(ValueError):
                        validate_manifest(manifest)
                    with self.assertRaises(ValueError):
                        install_assets(json.dumps(subset).encode(), Path(directory))

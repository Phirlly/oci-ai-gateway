"""Console ZIP is standalone and cannot be mistaken for a legacy controller archive."""

import io
import json
import unittest
import zipfile
from hashlib import sha256
from pathlib import Path

from deployment.console_package import ConsolePackage
from deployment.credential_errors import DeliveryError
from deployment.foundation_package import archive_digest
from runtime.source_archive import load_manifest

ROOT = Path(__file__).resolve().parents[3]


class ConsolePackageTests(unittest.TestCase):
    def test_zip_has_console_root_and_hashes_all_installed_assets(self):
        package = ConsolePackage.build(ROOT, repository="synthetic/gateway", commit="a" * 40)
        with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
            names = archive.namelist()
            self.assertIn("schema.yaml", names)
            self.assertIn("provider-secrets.tf", names)
            self.assertIn("gateway/cloud-compute.tf", names)
            self.assertIn('source = "./gateway"', archive.read("main.tf").decode())
            self.assertNotIn("../infra", archive.read("main.tf").decode())
            self.assertFalse(any(name.startswith(("docs/", "tests/", ".git/")) for name in names))
            manifest = load_manifest(archive.read("source.json"))
            self.assertIn("demo/support-requests.json", manifest["files"])
            self.assertIn("runtime/console_bootstrap.py", manifest["files"])
            self.assertNotIn("runtime/systemd/oci-ai-gateway-native-bootstrap.service", manifest["files"])
            for name, expected in manifest["files"].items():
                self.assertEqual(sha256(archive.read(name)).hexdigest(), expected)
            assets = {name: archive.read(name).decode() for name in manifest["files"]}
            self.assertLessEqual(len(json.dumps(assets).encode()), 256 * 1024)
        with self.assertRaises(DeliveryError):
            archive_digest(package.content)

    def test_archive_is_deterministic(self):
        first = ConsolePackage.build(ROOT, repository="synthetic/gateway", commit="a" * 40)
        second = ConsolePackage.build(ROOT, repository="synthetic/gateway", commit="a" * 40)
        self.assertEqual(first.content, second.content)

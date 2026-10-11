"""Schema4 archives are distinct; source manifests support either host startup path."""

import io
import json
import unittest
import zipfile
from pathlib import Path

from deployment.optional_package import OptionalPackage
from deployment.console_package import ConsolePackage
from deployment.foundation_package import FoundationPackage, NATIVE_MEMBERS
from runtime.source_archive import load_manifest

ROOT = Path(__file__).resolve().parents[3]


class OptionalPackageTests(unittest.TestCase):
    def test_distinct_version_and_manifests_have_no_conflicting_host_guard(self):
        for package_type, manifest_name in ((OptionalPackage, "runtime/source.json"), (ConsolePackage, "source.json")):
            with self.subTest(package=package_type.__name__):
                package = package_type.build(ROOT, repository="synthetic/gateway", commit="a" * 40)
                with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
                    names = set(archive.namelist())
                    manifest = load_manifest(archive.read(manifest_name))
                    self.assertNotEqual(names, NATIVE_MEMBERS)
                    for module in ("optional_startup.py", "optional_bundle.py", "provider_selection.py", "compose.cloud.yaml"):
                        self.assertIn("runtime/" + module, manifest["files"])
                    self.assertNotIn("runtime/systemd/docker-native.conf", manifest["files"])
                    self.assertNotIn("runtime/systemd/docker-guard.conf", manifest["files"])
                    assets = {name: archive.read(name).decode() for name in manifest["files"]}
                    self.assertLessEqual(len(json.dumps(assets).encode()), 256 * 1024)
                if package_type is OptionalPackage:
                    recovered = FoundationPackage(package.content)
                    self.assertEqual(recovered.schema_version, 4)
                    self.assertTrue(recovered.is_gateway)

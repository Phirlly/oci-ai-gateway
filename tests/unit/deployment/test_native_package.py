"""Native archives bind a public commit to exact sources and preserve legacy readers."""

import io
import json
from hashlib import sha256
import tempfile
import unittest
import zipfile
from pathlib import Path

from deployment.credential_errors import DeliveryError
from deployment.foundation_package import FoundationPackage, GatewayPackage, NATIVE_FILES
from deployment.native_package import SOURCE_EXCLUSIONS, NativePackage


class NativePackageTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for source in NATIVE_FILES.values():
            path = self.root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic " + source)

    def build(self):
        return NativePackage.build(self.root, repository="synthetic/gateway", commit="a" * 40)

    def test_source_manifest_matches_every_attested_runtime_file(self):
        package = self.build()
        self.assertEqual(package.schema_version, 3)
        self.assertTrue(package.is_gateway)
        with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
            payload = json.loads(archive.read("runtime/source.json"))
            expected = {name: sha256(archive.read(name)).hexdigest() for name in NATIVE_FILES
                        if name.startswith("runtime/") and name not in SOURCE_EXCLUSIONS}
            self.assertEqual(payload["files"], expected)
            self.assertIn("runtime/litellm_oci.patch", payload["files"])
            self.assertIn("runtime/LITELLM_LICENSE", payload["files"])
            self.assertNotIn("runtime/source.json", payload["files"])
        self.assertEqual(self.build().content, package.content)
        self.assertEqual(FoundationPackage(package.content).schema_version, 3)

    def test_original_member_sets_remain_distinct(self):
        self.assertEqual(GatewayPackage.build(self.root).schema_version, 2)
        self.assertEqual(FoundationPackage.build(self.root / "infra").schema_version, 1)

    def test_unlisted_files_and_stale_generated_payload_are_never_inputs(self):
        before = self.build()
        (self.root / "runtime/source.json").write_bytes(b"stale-sentinel")
        (self.root / "runtime/private.env").write_text("private-sentinel")
        after = self.build()
        self.assertEqual(before.content, after.content)
        self.assertNotIn(b"sentinel", after.content)

    def test_partial_native_manifest_is_rejected(self):
        package = self.build()
        stream = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(package.content)) as source, zipfile.ZipFile(stream, "w") as target:
            for name in source.namelist():
                if name != "runtime/oci_signing_client.py":
                    target.writestr(name, source.read(name))
        with self.assertRaises(DeliveryError):
            FoundationPackage(stream.getvalue())

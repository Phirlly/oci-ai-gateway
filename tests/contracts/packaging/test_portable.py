"""Extract each supported package outside the checkout and validate with Terraform1.5.7."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from deployment.foundation_package import FoundationPackage, GatewayPackage
from deployment.native_package import NativePackage
from deployment.console_package import ConsolePackage
from deployment.optional_package import OptionalPackage

ROOT = Path(__file__).resolve().parents[3]


class PortablePackageContracts(unittest.TestCase):
    def test_console_archive_validates_outside_the_checkout(self):
        package = ConsolePackage.build(ROOT, repository="synthetic/gateway", commit="a" * 40)
        with tempfile.TemporaryDirectory(prefix="gateway-console-package-") as directory:
            extracted = Path(directory)
            with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
                archive.extractall(extracted)  # Built from the explicit Console package allowlist.
            self.terraform(extracted, "init", "-backend=false", "-input=false", "-lockfile=readonly",
                           "-plugin-dir=" + str(ROOT / "infra/.terraform/providers"))
            self.terraform(extracted, "validate", "-no-color")
            for group in ("runtime", "demo"):
                for path in (extracted / group).glob("*.py"):
                    compile(path.read_text(), path.name, "exec")
            self.assertFalse((extracted / "docs").exists())
            self.assertTrue((extracted / "schema.yaml").is_file())
            self.runtime_imports(extracted)

    def runtime_imports(self, extracted):
        modules = ["runtime." + path.stem for path in (extracted / "runtime").glob("*.py")
                   if path.stem not in {"__init__", "oci_gateway_callback", "oci_gateway_loader"}]
        # Isolated Python has no checkout path; this catches omitted shared imports.
        command = "import importlib,sys; sys.path.insert(0,sys.argv[1]); [importlib.import_module(name) for name in sys.argv[2:]]"
        result = subprocess.run([sys.executable, "-I", "-c", command, str(extracted), *modules],
                                cwd=extracted, capture_output=True, text=True, timeout=30,
                                env={"PATH": os.environ["PATH"], "LITELLM_LOCAL_MODEL_COST_MAP": "True"})
        self.assertEqual(result.returncode, 0, "Extracted runtime import failed: " + result.stderr)

    def terraform(self, directory, *arguments):
        binary = os.environ.get("GATEWAY_TERRAFORM_15", str(ROOT / ".cache/terraform/1.5.7/terraform"))
        result = subprocess.run([binary, "-chdir=" + str(directory), *arguments],
                                capture_output=True, text=True, timeout=180,
                                env={**os.environ, "TF_IN_AUTOMATION": "1", "TF_INPUT": "0"})
        self.assertEqual(result.returncode, 0, "Portable Terraform command failed: " + arguments[0])
        return result.stdout

    def test_legacy_and_gateway_archives_are_self_contained(self):
        for package in (FoundationPackage.build(ROOT / "infra"), GatewayPackage.build(ROOT),
                        NativePackage.build(ROOT, repository="synthetic/gateway", commit="a" * 40),
                        OptionalPackage.build(ROOT, repository="synthetic/gateway", commit="a" * 40)):
            with self.subTest(gateway=package.is_gateway), tempfile.TemporaryDirectory(prefix="gateway-package-") as directory:
                extracted = Path(directory)
                with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
                    archive.extractall(extracted)  # Constructor already checked the exact member allowlist.
                foundation = extracted / "foundation"
                version = self.terraform(foundation, "version")
                self.assertIn("Terraform v1.5.7", version)
                self.terraform(foundation, "init", "-backend=false", "-input=false", "-lockfile=readonly",
                               "-plugin-dir=" + str(ROOT / "infra/.terraform/providers"))
                self.terraform(foundation, "validate", "-no-color")
                if package.is_gateway:
                    for path in (extracted / "runtime").glob("*.py"):
                        compile(path.read_text(), path.name, "exec")
                    self.runtime_imports(extracted)
                self.assertFalse((extracted / "docs").exists())
                self.assertFalse((extracted / "deployment.tfvars.json").exists())

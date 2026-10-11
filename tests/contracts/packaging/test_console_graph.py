"""Check the real Console/Compute graph without configuring an OCI provider."""

import io
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from deployment.console_package import ConsolePackage

ROOT = Path(__file__).resolve().parents[3]


class ConsoleDependencyContracts(unittest.TestCase):
    def test_late_context_cannot_be_referenced_by_early_bootstrap(self):
        package = ConsolePackage.build(ROOT, repository="synthetic/gateway", commit="a" * 40)
        with tempfile.TemporaryDirectory(prefix="gateway-console-graph-") as directory:
            extracted = Path(directory)
            with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
                archive.extractall(extracted)
            result = self.terraform(extracted, "init", "-backend=false", "-input=false", "-lockfile=readonly",
                                    "-plugin-dir=" + str(ROOT / "infra/.terraform/providers"))
            self.assertEqual(result.returncode, 0, "Fixture initialization failed")
            self.assertEqual(self.terraform(extracted, "validate", "-no-color").returncode, 0,
                             "The unmodified composed graph must validate first")

            # Mutation is restricted to this disposable extracted package.
            main = extracted / "main.tf"
            original = main.read_text()
            marker = "  console_settings = {\n"
            self.assertEqual(original.count(marker), 1)
            main.write_text(original.replace(marker, marker + "    context_secret_ocid = oci_vault_secret.context.id\n"))
            invalid = self.terraform(extracted, "validate", "-no-color")
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("Cycle:", invalid.stdout + invalid.stderr)
            self.assertIn("oci_vault_secret.context", invalid.stdout + invalid.stderr)

    @staticmethod
    def terraform(directory, *arguments):
        binary = os.environ.get("GATEWAY_TERRAFORM_15", str(ROOT / ".cache/terraform/1.5.7/terraform"))
        return subprocess.run([binary, "-chdir=" + str(directory), *arguments],
                              capture_output=True, text=True, timeout=180,
                              env={**os.environ, "TF_IN_AUTOMATION": "1", "TF_INPUT": "0",
                                   "OCI_CONFIG_FILE_PROFILE": "GATEWAY_OFFLINE_NO_PROFILE",
                                   "TF_VAR_config_file_profile": "GATEWAY_OFFLINE_NO_PROFILE"})

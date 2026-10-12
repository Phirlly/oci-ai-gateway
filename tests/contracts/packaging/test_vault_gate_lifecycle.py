"""Prove provisioner ordering, recovery and Destroy using no OCI resources."""

import shutil
import tempfile
import unittest
from pathlib import Path

from .vault_gate_fixture import prepare, resources, terraform


class VaultGateLifecycleContracts(unittest.TestCase):
    def test_relocated_plan_noop_replacement_and_destroy(self):
        with tempfile.TemporaryDirectory(prefix="vault-gate-") as root:
            original = Path(root) / "plan"
            original.mkdir()
            prepare(original)
            terraform(original, "init", "-backend=false", "-input=false")
            terraform(original, "plan", "-out=saved.plan", "-input=false")
            applied = Path(root) / "apply"
            shutil.copytree(original, applied)
            shutil.rmtree(original)  # The Plan runner's directory is gone.
            terraform(applied, "apply", "-input=false", "saved.plan")
            first = resources(applied)
            self.assertIn("terraform_data.key", first)
            self.assertEqual((applied / "calls").read_text(), "probe\n")
            terraform(applied, "apply", "-auto-approve", "-input=false")
            self.assertEqual(resources(applied), first)
            self.assertEqual((applied / "calls").read_text(), "probe\n")
            terraform(applied, "apply", "-auto-approve", "-input=false", "-var=fixture_vault_id=vault-two")
            second = resources(applied)
            self.assertNotEqual(first["terraform_data.vault_endpoint[0]"]["values"]["id"],
                                second["terraform_data.vault_endpoint[0]"]["values"]["id"])
            self.assertEqual((applied / "calls").read_text(), "probe\nprobe\n")
            (applied / "probe script.py").unlink()
            terraform(applied, "destroy", "-auto-approve", "-input=false")
            self.assertEqual(resources(applied), {})
            self.assertEqual((applied / "calls").read_text(), "probe\nprobe\n")

    def test_failed_gate_blocks_key_then_retries_or_destroys(self):
        for recover in (False, True):
            with self.subTest(recover=recover), tempfile.TemporaryDirectory(prefix="vault-failed-") as root:
                directory = Path(root)
                prepare(directory)
                (directory / "fail").touch()
                terraform(directory, "init", "-backend=false", "-input=false")
                terraform(directory, "apply", "-auto-approve", "-input=false", success=False)
                self.assertNotIn("terraform_data.key", resources(directory))
                if recover:
                    (directory / "fail").unlink()
                    terraform(directory, "apply", "-auto-approve", "-input=false")
                    self.assertIn("terraform_data.key", resources(directory))
                before = (directory / "calls").read_text()
                (directory / "probe script.py").unlink()
                terraform(directory, "destroy", "-auto-approve", "-input=false")
                self.assertEqual(resources(directory), {})
                self.assertEqual((directory / "calls").read_text(), before)

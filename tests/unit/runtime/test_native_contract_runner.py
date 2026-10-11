"""The native adapter runner removes only its own disposable container."""

import subprocess
import unittest
from unittest.mock import patch

from tests.contracts.native_oci.container import run_container


class NativeContainerCleanup(unittest.TestCase):
    def test_timeout_still_removes_and_verifies_exact_owned_name(self):
        with patch("tests.contracts.native_oci.container.subprocess.run", side_effect=[
                subprocess.TimeoutExpired("docker", 90),
                subprocess.CompletedProcess([], 0),
                subprocess.CompletedProcess([], 0, stdout=""),
        ]) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                run_container(["-m", "unittest"])
        commands = [call.args[0] for call in run.call_args_list]
        name = commands[0][commands[0].index("--name") + 1]
        self.assertTrue(name.startswith("gateway-native-contract-"))
        self.assertEqual(commands[1][-3:], ["rm", "--force", name])
        self.assertEqual(commands[2][-1], "name=^/" + name + "$")
        self.assertIn("--network=none", commands[0])
        self.assertIn("--read-only", commands[0])

    def test_remaining_container_cannot_report_success(self):
        with patch("tests.contracts.native_oci.container.subprocess.run", side_effect=[
                subprocess.CompletedProcess([], 0),
                subprocess.CompletedProcess([], 0),
                subprocess.CompletedProcess([], 0, stdout="remaining"),
        ]):
            with self.assertRaisesRegex(RuntimeError, "Owned native contract container remains"):
                run_container([])

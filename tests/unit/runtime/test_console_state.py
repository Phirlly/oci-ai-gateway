"""Durable Console runs reject identity changes and uncertain sample replay."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.console_state import ConsoleState
from runtime.gateway_http import GatewayError
from .console_fixture import context


class ConsoleStateTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.state = ConsoleState(self.directory, context(), "ocid1.vaultsecret.oc1.iad.context")

    def test_new_run_advances_without_resetting_identity(self):
        self.assertIsNone(self.state.load())
        record = self.state.begin()
        self.assertEqual((record["run"], record["phase"]), (1, "preparing"))
        next_run = ConsoleState(self.directory, context(2), "ocid1.vaultsecret.oc1.iad.context")
        self.assertEqual(next_run.begin()["run"], 2)
        self.assertEqual(next_run.load()["identity"], record["identity"])

    def test_identity_changes_and_rollback_never_reset_state(self):
        self.state.begin()
        changed = context(2)
        changed["public_ip"] = "8.8.8.8"
        with self.assertRaises(GatewayError):
            ConsoleState(self.directory, changed, "ocid1.vaultsecret.oc1.iad.context").begin()
        next_run = ConsoleState(self.directory, context(2), "ocid1.vaultsecret.oc1.iad.context")
        next_run.begin()
        with self.assertRaises(GatewayError):
            self.state.begin()

    def test_crash_before_atomic_publication_retains_previous_record(self):
        record = self.state.begin()
        record["phase"] = "started"
        record["external_version"] = 1
        with patch("runtime.console_state.os.replace", side_effect=OSError("interrupted")) as replace:
            with self.assertRaises(GatewayError):
                self.state.save(record)
            replace.assert_called_once()
        self.assertEqual(self.state.load()["phase"], "preparing")

    def test_symlink_and_permissive_records_are_rejected(self):
        target = self.directory / "foreign"
        target.write_text("{}")
        path = self.directory / "console-state.json"
        path.symlink_to(target)
        with self.assertRaises(GatewayError):
            self.state.load()
        path.unlink()
        self.state.begin()
        path.chmod(0o644)
        with self.assertRaises(GatewayError):
            self.state.load()

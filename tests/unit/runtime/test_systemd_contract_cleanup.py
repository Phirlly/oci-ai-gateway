"""Systemd contract interruption and cleanup failures preserve exact recovery."""

import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tests.contracts.signing_systemd.fixture import SystemdSocket


class SystemdContractCleanupTests(unittest.TestCase):
    def test_stopped_unloaded_units_do_not_prevent_owned_file_cleanup(self):
        owner = SystemdSocket()
        with tempfile.TemporaryDirectory() as directory:
            owner.directory = Path(directory) / "inputs"
            owner.directory.mkdir()
            owner.units = ["/run/systemd/system/" + owner.name + "." + suffix for suffix in ("socket", "service")]
            def control(*args):
                if args[0] == "reset-failed":
                    raise RuntimeError("Stopped unit no longer loaded")
                return ""
            with patch.object(owner, "control", side_effect=control), \
                    patch("tests.contracts.signing_systemd.fixture.run_command") as run, \
                    patch("tests.contracts.signing_systemd.fixture.subprocess.run",
                          return_value=Mock(returncode=1)):
                owner.cleanup()
            run.assert_called_once_with(["sudo", "-n", "rm", "--", *owner.units])
            self.assertFalse(owner.directory.exists())

    def test_failed_container_cleanup_reports_owned_paths_and_preserves_inputs(self):
        owner = SystemdSocket()
        with tempfile.TemporaryDirectory() as directory:
            owner.directory = Path(directory)
            marker = owner.directory / "unit-input"
            marker.write_text("synthetic")
            owner.container = True
            with patch("tests.contracts.signing_systemd.fixture.run_command", side_effect=RuntimeError("failed")), \
                    self.assertRaises(RuntimeError) as raised:
                owner.__exit__(None, None, None)
            self.assertIn(owner.name, str(raised.exception))
            self.assertIn(str(owner.directory), str(raised.exception))
            self.assertIn(owner.socket_dir, str(raised.exception))
            self.assertTrue(marker.exists())

    def test_runner_turns_sigterm_into_context_unwinding(self):
        from tests.contracts.signing_systemd.__main__ import main
        result = Mock()
        result.result.wasSuccessful.return_value = True
        with patch("tests.contracts.signing_systemd.__main__.signal.signal") as register, \
                patch("tests.contracts.signing_systemd.__main__.unittest.main", return_value=result):
            self.assertEqual(main(), 0)
        self.assertEqual(register.call_args.args[0], signal.SIGTERM)
        with self.assertRaises(KeyboardInterrupt):
            register.call_args.args[1](signal.SIGTERM, None)

    def test_sigterm_during_owned_context_runs_cleanup(self):
        from tests.contracts.signing_systemd.__main__ import main
        owner = SystemdSocket()
        with patch.object(SystemdSocket, "__enter__", return_value=owner), \
                patch.object(owner, "cleanup") as cleanup, \
                patch("tests.contracts.signing_systemd.__main__.signal.signal") as register:
            def run_suite(**kwargs):
                with owner:
                    register.call_args.args[1](signal.SIGTERM, None)
            with patch("tests.contracts.signing_systemd.__main__.unittest.main", side_effect=run_suite):
                self.assertEqual(main(), 130)
        cleanup.assert_called_once_with()

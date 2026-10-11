"""Console lifecycle uses explicit run numbers to prevent implicit billed replays."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.console_runner import run_console
from runtime.console_secrets import Secret
from runtime.console_state import ConsoleState
from runtime.gateway_http import GatewayError
from .console_fixture import context, settings

CONTEXT_ID = "ocid1.vaultsecret.oc1.iad.context"


class ConsoleRunnerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.public = self.root / "public"
        self.current = context()
        self.key, self.version = b"synthetic-external-key", 1
        self.read = self.enterContext(patch("runtime.console_runner.read_secret", side_effect=self.secret))
        self.enterContext(patch("runtime.console_runner.instance_id", return_value=self.current["instance_ocid"]))
        self.edge = self.enterContext(patch("runtime.console_runner.start_edge"))
        self.activate = self.enterContext(patch("runtime.console_runner.activate_gateway"))
        self.presenter = self.enterContext(patch("runtime.console_runner.initialize_presenter"))
        self.health = self.enterContext(patch("runtime.console_runner.check_health"))
        self.login = self.enterContext(patch("runtime.console_runner.presenter_client"))
        self.verify = self.enterContext(patch("runtime.console_runner.verify_demo", return_value={
            "ready": True, "login": "PASS", "model_access": "PASS", "admin_denial": "PASS",
            "samples": [{"status": "PASS"} for _ in range(8)]}))

    def secret(self, config, *, secret_id=None, context=False):
        if context:
            return Secret(json.dumps(self.current).encode(), self.current["verification_run"], CONTEXT_ID)
        if secret_id == config["presenter_secret_ocid"]:
            return Secret(b'{"password":"Demo1!SyntheticPassword123"}', 1, secret_id)
        return Secret(self.key, self.version, secret_id)

    def run_once(self):
        return run_console(settings(), self.private, self.public)

    def status(self):
        return json.loads((self.public / "status.json").read_text())["status"]

    def test_missing_key_starts_edge_then_waits_without_model_calls(self):
        self.key = b"UNCONFIGURED"
        self.run_once()
        self.edge.assert_called_once()
        self.activate.assert_not_called()
        self.verify.assert_not_called()
        self.assertEqual(self.status(), "WAITING_CREDENTIALS")

    def test_completed_run_does_not_repeat_setup_or_calls(self):
        self.run_once()
        self.assertEqual(self.status(), "READY")
        self.run_once()
        self.verify.assert_called_once()
        self.activate.assert_called_once()
        self.presenter.assert_called_once()

    def test_public_tls_can_become_ready_without_consuming_a_verification_run(self):
        self.health.side_effect = GatewayError("TLS certificate is not ready")
        self.run_once()
        self.verify.assert_not_called()
        self.assertEqual(self.status(), "WAITING_FRONTEND")
        self.assertEqual(ConsoleState(self.private, self.current, CONTEXT_ID).load()["phase"], "active")
        self.health.side_effect = None
        self.run_once()
        self.verify.assert_called_once()
        self.activate.assert_called_once()
        self.assertEqual(self.status(), "READY")

    def test_new_run_activates_corrected_key_and_preserves_internal_credentials(self):
        self.run_once()
        original = (self.private / "console-credentials.json").read_bytes()
        self.current = context(2)
        self.key, self.version = b"corrected-key", 2
        self.run_once()
        self.assertEqual(self.verify.call_count, 2)
        self.assertIn("corrected-key", (self.private / "gateway-secrets.json").read_text())
        self.assertEqual((self.private / "console-credentials.json").read_bytes(), original)

    def test_activation_interruption_resumes_preparation_before_verification(self):
        self.activate.side_effect = GatewayError("synthetic activation failure")
        self.run_once()
        self.verify.assert_not_called()
        self.assertEqual(self.status(), "ERROR")
        self.activate.side_effect = None
        self.run_once()
        self.assertEqual(self.activate.call_count, 2)
        self.verify.assert_called_once()

    def test_crash_after_started_never_replays_calls(self):
        self.verify.side_effect = SystemExit("synthetic process interruption")
        with self.assertRaises(SystemExit):
            self.run_once()
        self.run_once()
        self.verify.assert_called_once()
        self.assertEqual(self.status(), "INTERRUPTED")
        state = ConsoleState(self.private, self.current, CONTEXT_ID).load()
        self.assertEqual(state["phase"], "started")

    def test_failed_samples_require_explicit_run_and_clear_old_ready(self):
        self.run_once()
        self.current = context(2)
        self.verify.return_value["samples"][0]["status"] = "ERROR"
        self.verify.return_value["ready"] = False
        self.run_once()
        self.assertEqual(self.status(), "FAILED")
        self.run_once()
        self.assertEqual(self.verify.call_count, 2)

    def test_changed_secret_during_interrupted_preparation_requires_new_run(self):
        self.activate.side_effect = GatewayError("interrupted")
        self.run_once()
        self.key, self.version = b"changed", 2
        self.activate.side_effect = None
        self.run_once()
        self.verify.assert_not_called()
        self.assertEqual(self.activate.call_count, 1)
        self.assertEqual(self.status(), "ERROR")

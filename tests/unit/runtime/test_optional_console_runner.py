"""Console preparation pins all selected keys; a separate invocation bills samples."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.console_runner import run_console
from runtime.console_secrets import Secret
from runtime.gateway_http import GatewayError
from .optional_console_fixture import context
from .optional_fixture import SUBSETS


class OptionalConsoleRunnerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.current = context()
        self.versions = {"anthropic": 1, "openai": 1}
        self.unconfigured = set()
        self.read = self.enterContext(patch("runtime.console_runner.read_secret", side_effect=self.secret))
        self.enterContext(patch("runtime.console_runner.instance_id", return_value=self.current["instance_ocid"]))
        self.edge = self.enterContext(patch("runtime.console_runner.start_edge"))
        self.activate = self.enterContext(patch("runtime.console_runner.activate_gateway"))
        self.enterContext(patch("runtime.console_runner.initialize_presenter"))
        self.enterContext(patch("runtime.console_runner.check_health"))
        self.enterContext(patch("runtime.console_runner.presenter_client"))
        self.verify = self.enterContext(patch("runtime.console_runner.verify_demo", side_effect=self.report))

    def secret(self, config, *, secret_id=None, context=False):
        if context:
            return Secret(json.dumps(self.current).encode(), self.current["verification_run"], "ocid1.vaultsecret.oc1.iad.context")
        if secret_id == config["presenter_secret_ocid"]:
            return Secret(b'{"password":"Synthetic9!Password"}', 1, secret_id)
        provider = next(name for name, identifier in config["provider_secrets"].items() if identifier == secret_id)
        content = b"UNCONFIGURED" if provider in self.unconfigured else ("key-" + provider + str(self.versions[provider])).encode()
        return Secret(content, self.versions[provider], secret_id)

    def report(self, public, presenter, password):
        return {"ready": True, "login": "PASS", "model_access": "PASS", "admin_denial": "PASS",
                "samples": [{"status": "PASS"} for _ in range(4 * len(presenter.models))]}

    def run_once(self, name="private"):
        private = self.root / name
        private.mkdir(mode=0o700, exist_ok=True)
        run_console(self.current["settings"], private, self.root / "status")
        return json.loads((self.root / "status/status.json").read_text())

    def test_all_subsets_prepare_without_billing_then_verify_once(self):
        for index, providers in enumerate(SUBSETS):
            with self.subTest(providers=providers):
                self.current = context(providers)
                self.verify.reset_mock()
                self.activate.reset_mock()
                self.read.reset_mock()
                self.run_once(str(index))
                self.verify.assert_not_called()
                report = self.run_once(str(index))
                self.assertEqual((report["status"], report["samples_total"]), ("READY", 4 * len(providers)))
                self.run_once(str(index))
                self.verify.assert_called_once()
                self.activate.assert_called_once()
                selected_ids = set(self.current["settings"]["provider_secrets"].values())
                reads = {call.kwargs["secret_id"] for call in self.read.call_args_list if "secret_id" in call.kwargs}
                self.assertEqual(reads, selected_ids | {self.current["settings"]["presenter_secret_ocid"]})

    def test_one_missing_key_never_publishes_partial_credentials(self):
        self.unconfigured = {"openai"}
        self.assertEqual(self.run_once()["status"], "WAITING_CREDENTIALS")
        self.activate.assert_not_called()
        self.assertFalse((self.root / "private/gateway-secrets.json").exists())

    def test_changed_key_after_failed_activation_requires_explicit_new_run(self):
        self.activate.side_effect = GatewayError("synthetic activation failure")
        self.run_once()
        before = (self.root / "private/gateway-secrets.json").read_bytes()
        self.versions["openai"] = 2
        self.activate.side_effect = None
        self.assertEqual(self.run_once()["status"], "ERROR")
        self.assertEqual((self.root / "private/gateway-secrets.json").read_bytes(), before)
        self.activate.assert_called_once()
        self.verify.assert_not_called()

    def test_interrupted_verification_never_replays_automatically(self):
        self.run_once()
        self.verify.side_effect = SystemExit("synthetic interruption")
        with self.assertRaises(SystemExit):
            self.run_once()
        self.assertEqual(self.run_once()["status"], "INTERRUPTED")
        self.verify.assert_called_once()

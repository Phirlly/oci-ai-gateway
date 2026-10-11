"""Public status contains fixed categories and last-verification evidence only."""

import json
import tempfile
import unittest
from pathlib import Path

from runtime.console_status import publish_status
from runtime.runtime_files import caddy_config


class ConsoleStatusTests(unittest.TestCase):
    def test_new_run_replaces_ready_and_never_publishes_private_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status"
            publish_status(path, "READY", {"run": 1, "passed": 8, "finished_at": "2026-10-11T12:00:00Z",
                                            "credentials": "synthetic-secret"})
            value = json.loads((path / "status.json").read_text())
            self.assertEqual(value["status"], "READY")
            self.assertEqual(value["meaning"], "Last verification result; not continuous health")
            self.assertNotIn("synthetic-secret", (path / "status.json").read_text())
            publish_status(path, "WAITING_CREDENTIALS", {"run": 2, "passed": 0, "finished_at": ""})
            value = json.loads((path / "status.json").read_text())
            self.assertEqual((value["status"], value["verification_run"]), ("WAITING_CREDENTIALS", 2))
            self.assertEqual((path / "status.json").stat().st_mode & 0o777, 0o644)

    def test_status_route_is_explicit_and_does_not_expose_runtime_directory(self):
        config = caddy_config("8.8.4.4", console=True)
        self.assertIn("handle /deployment-status", config)
        self.assertIn("/srv/gateway-status", config)
        self.assertNotIn("/var/lib/oci-ai-gateway", config)
        self.assertIn("reverse_proxy gateway:4000", config)
        self.assertNotIn("file_server", caddy_config("8.8.4.4"))

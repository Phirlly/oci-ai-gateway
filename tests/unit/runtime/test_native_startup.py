"""Native startup publishes verified files before socket and application startup."""

import json
import subprocess
from unittest.mock import patch

from runtime.gateway_http import GatewayError
from runtime.native_startup import start_native_services
from .overlay_fixture import OverlayCase


class NativeStartupTests(OverlayCase):
    def setUp(self):
        super().setUp()
        self.state = self.directory / "state"
        self.state.mkdir(mode=0o700)
        self.enterContext(patch("runtime.native_startup.ensure_native_dependencies"))
        self.commands = []

        def run(command, phase, timeout, **kwargs):
            self.commands.append(command)
            if "up" in command:
                self.assertTrue((self.state / "oci-generic.py").is_file())
                self.assertTrue(any("enable" in row for row in self.commands))
            return subprocess.CompletedProcess(command, 0, json.dumps(self.record), "")

        self.run = self.enterContext(patch("runtime.native_startup._run", side_effect=run))

    def test_verified_overlay_and_socket_precede_compose_and_survive_rerun(self):
        start_native_services(self.state)
        before = {p.name: (p.stat().st_ino, p.read_text()) for p in self.state.iterdir()}
        start_native_services(self.state)
        self.assertEqual(before, {p.name: (p.stat().st_ino, p.read_text()) for p in self.state.iterdir()})
        self.assertEqual({p.name for p in self.state.iterdir()}, {"oci-generic.py", "oci-transformation.py"})
        export = next(row for row in self.commands if "run" in row)
        self.assertEqual(export[export.index("--network") + 1], "none")
        self.assertIn("--read-only", export)
        self.assertTrue(any("rm" in row for row in self.commands))

    def test_invalid_export_never_enables_socket_or_starts_gateway(self):
        self.record["files"][next(iter(self.record["files"]))] = "changed source"
        with self.assertRaises(GatewayError):
            start_native_services(self.state)
        self.assertFalse(list(self.state.iterdir()))
        self.assertFalse(any("up" in row or "enable" in row for row in self.commands))
        self.assertTrue(any("rm" in row for row in self.commands))

    def test_export_failure_attempts_owned_container_cleanup_and_stops(self):
        def fail(command, *args, **kwargs):
            self.commands.append(command)
            if "run" in command:
                raise GatewayError("Export timed out")
            return subprocess.CompletedProcess(command, 0, "", "")
        self.run.side_effect = fail
        with self.assertRaises(GatewayError):
            start_native_services(self.state)
        self.assertTrue(any("rm" in row for row in self.commands))
        self.assertFalse(any("up" in row for row in self.commands))

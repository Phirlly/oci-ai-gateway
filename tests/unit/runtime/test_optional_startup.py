"""Only native selections install a socket dependency; derived guards stay immutable."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.optional_startup import configure_host
from runtime.console_services import activate_gateway
from .optional_fixture import SUBSETS, settings


class OptionalStartupTests(unittest.TestCase):
    def test_guard_selection_is_repeatable_and_rejects_changed_bytes(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                configure_host(settings(providers), root)
                path = root / "etc/systemd/system/docker.service.d/10-gateway-guard.conf"
                self.assertEqual("Requires=oci-ai-gateway-signing.socket" in path.read_text(), "oci" in providers)
                self.assertIn("runtime.host_firewall", path.read_text())
                inode = path.stat().st_ino
                configure_host(settings(providers), root)
                self.assertEqual(path.stat().st_ino, inode)
                path.write_text("foreign guard")
                with self.assertRaises(ValueError):
                    configure_host(settings(providers), root)
                self.assertEqual(path.read_text(), "foreign guard")

    @patch("runtime.console_services._run")
    @patch("runtime.console_services.start_native_services")
    def test_external_only_activation_skips_native_setup_and_socket_mounts(self, native, run):
        activate_gateway(Path("/synthetic"), native=False)
        native.assert_not_called()
        commands = [call.args[0] for call in run.call_args_list]
        self.assertTrue(all(any(item.endswith("compose.cloud.yaml") for item in cmd) for cmd in commands))
        self.assertTrue(all(not any(item.endswith("compose.native.yaml") for item in cmd) for cmd in commands))

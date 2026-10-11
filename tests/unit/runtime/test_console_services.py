"""Edge starts independently; key activation recreates only the gateway container."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.console_services import start_edge, activate_gateway


class ConsoleServiceTests(unittest.TestCase):
    @patch("runtime.console_services._run")
    def test_edge_does_not_start_gateway_or_database(self, run):
        with tempfile.TemporaryDirectory() as directory:
            start_edge(Path(directory), "8.8.4.4")
            self.assertTrue((Path(directory) / "Caddyfile").exists())
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[-1][-4:], ["up", "-d", "--no-deps", "edge"])
        self.assertTrue(all("gateway" not in cmd and "database" not in cmd for cmd in commands))

    @patch("runtime.console_services._run")
    @patch("runtime.console_services.start_native_services")
    def test_key_refresh_recreates_gateway_after_native_services(self, start, run):
        events = []
        start.side_effect = lambda *a, **k: events.append("start")
        run.side_effect = lambda *a, **k: events.append("recreate")
        activate_gateway(Path("/synthetic"))
        self.assertEqual(events, ["start", "recreate"])
        command = run.call_args.args[0]
        self.assertIn("--force-recreate", command)
        self.assertIn("--no-deps", command)
        self.assertEqual(command[-1], "gateway")

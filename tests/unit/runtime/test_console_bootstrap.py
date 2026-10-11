"""Direct bootstrap holds the same private host lock and keeps the retry timer active."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.console_bootstrap import main
from .console_fixture import settings


class ConsoleBootstrapTests(unittest.TestCase):
    def test_optional_active_verification_skips_dependency_preparation(self):
        from .optional_console_fixture import settings as optional_settings
        with patch("runtime.console_bootstrap.os.geteuid", return_value=0), \
                patch("runtime.console_bootstrap.load_config", return_value=optional_settings()), \
                patch("runtime.console_bootstrap.locked_state"), \
                patch("runtime.console_bootstrap.read_record", return_value={"phase": "active"}), \
                patch("runtime.console_bootstrap.ensure_dependencies") as dependencies, \
                patch("runtime.console_bootstrap.protect_metadata"), \
                patch("runtime.console_bootstrap.run_console") as run:
            self.assertEqual(main(), 0)
            dependencies.assert_not_called()
            run.assert_called_once()

    def test_entrypoint_verifies_private_settings_and_does_not_stop_timer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "settings.json"
            config.write_text(json.dumps(settings()))
            config.chmod(0o600)
            with patch("runtime.console_bootstrap.os.geteuid", return_value=0), \
                    patch("runtime.console_bootstrap.load_config", return_value=settings()), \
                    patch("runtime.console_bootstrap.locked_state") as lock, \
                    patch("runtime.console_bootstrap.ensure_dependencies"), \
                    patch("runtime.console_bootstrap.protect_metadata"), \
                    patch("runtime.console_bootstrap.run_console") as run, \
                    patch("runtime.host_commands.stop_bootstrap_timer") as stop:
                self.assertEqual(main(), 0)
                lock.assert_called_once()
                run.assert_called_once()
                stop.assert_not_called()

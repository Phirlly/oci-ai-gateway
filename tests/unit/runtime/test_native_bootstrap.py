"""Native initialization preserves ordering and completed presenter state."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.bootstrap import initialize
from runtime.runtime_bundle import BundlePending
from .bundle_fixture import INSTANCE, NOW
from .native_bundle_fixture import NATIVE_SETTINGS, native_bundle
from .presenter_fixture import AccountAPI


class NativeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.api = AccountAPI()
        self.enterContext(patch("runtime.bootstrap.ensure_dependencies"))
        self.guard = self.enterContext(patch("runtime.bootstrap.protect_metadata"))
        self.enterContext(patch("runtime.bootstrap.instance_id", return_value=INSTANCE))
        self.content = self.enterContext(patch("runtime.bootstrap.current_content", return_value=json.dumps(native_bundle()).encode()))
        self.enterContext(patch("runtime.bootstrap.PresenterAPI", return_value=self.api))
        self.legacy = self.enterContext(patch("runtime.bootstrap.start_services"))
        self.native = self.enterContext(patch("runtime.native_startup.start_native_services", side_effect=self.started))

    def started(self, directory):
        self.guard.assert_called()
        self.assertEqual(directory, self.root)
        self.assertTrue((self.root / "gateway.json").is_file())

    def initialize(self):
        initialize(NATIVE_SETTINGS, self.root, now=NOW)

    def test_native_starts_after_private_files_and_does_not_reset_completed_account(self):
        self.initialize()
        self.native.assert_called_once()
        self.legacy.assert_not_called()
        self.api.password = "Changed9!Password"
        self.content.reset_mock()
        self.initialize()
        self.content.assert_not_called()
        self.native.assert_called_once()
        self.assertEqual(self.api.password, "Changed9!Password")

    def test_pending_bundle_starts_neither_runtime(self):
        self.content.return_value = b"UNCONFIGURED"
        with self.assertRaises(BundlePending):
            self.initialize()
        self.native.assert_not_called()
        self.legacy.assert_not_called()

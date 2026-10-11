"""The host service accepts only private, bounded deployment settings."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from runtime.oci_signing_entrypoint import load_settings
from runtime.gateway_http import GatewayError
from .bundle_fixture import SETTINGS


class SigningSettingsTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "settings.json"
        self.path.write_text(json.dumps(SETTINGS))
        self.path.chmod(0o600)

    def load(self):
        return load_settings(self.path, expected_uid=os.geteuid())

    def test_loads_complete_private_settings(self):
        self.assertEqual(self.load(), SETTINGS)

    def test_rejects_group_readable_symlink_and_wrong_owner(self):
        self.path.chmod(0o640)
        with self.assertRaises(GatewayError):
            self.load()
        self.path.chmod(0o600)
        with self.assertRaises(GatewayError):
            load_settings(self.path, expected_uid=os.geteuid() + 1)
        target = self.path.with_suffix(".link")
        target.symlink_to(self.path)
        with self.assertRaises(GatewayError):
            load_settings(target, expected_uid=os.geteuid())

    def test_rejects_large_unknown_and_duplicate_fields(self):
        for content in (" " * 8193, json.dumps(SETTINGS | {"extra": "value"}),
                        json.dumps(SETTINGS)[:-1] + ', "schema_version": 1}'):
            with self.subTest(content=content[:40]):
                self.path.write_text(content)
                with self.assertRaises(GatewayError):
                    self.load()

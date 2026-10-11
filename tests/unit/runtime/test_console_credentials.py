"""Console credential creation is stable; only the external key may be refreshed."""

import tempfile
import unittest
from pathlib import Path

from runtime.console_credentials import internal_credentials, publish_credentials
from runtime.gateway_http import GatewayError


class ConsoleCredentialTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_internal_credentials_are_private_distinct_and_stable(self):
        original = internal_credentials(self.directory)
        self.assertEqual(internal_credentials(self.directory), original)
        self.assertEqual(len(set(original.values())), 3)
        self.assertEqual((self.directory / "console-credentials.json").stat().st_mode & 0o777, 0o600)

    def test_key_rotation_preserves_internal_values_and_refuses_foreign_file(self):
        credentials = internal_credentials(self.directory)
        publish_credentials(self.directory, {**credentials, "external_api_key": "first"})
        publish_credentials(self.directory, {**credentials, "external_api_key": "second"})
        path = self.directory / "gateway-secrets.json"
        self.assertIn('"second"', path.read_text())
        with self.assertRaises(GatewayError):
            publish_credentials(self.directory, {**credentials, "database_password": "changed", "external_api_key": "third"})
        self.assertIn('"second"', path.read_text())

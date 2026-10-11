"""Reject unsafe or ambiguous gateway configuration before callback startup."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.gateway_http import GatewayError
from runtime.oci_gateway_config import load_routes
from .native_config_fixture import gateway_config


class NativeGatewayConfigFile(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.directory / "config.json"
        self.path.write_text(json.dumps(gateway_config()))
        self.path.chmod(0o600)

    def test_private_config_uses_real_parser(self):
        self.assertEqual(load_routes(self.path).scope.model_id, "google.gemini-2.5-flash-lite")

    def test_missing_symlink_directory_and_wrong_owner_are_rejected(self):
        link = self.directory / "link"
        link.symlink_to(self.path)
        for path in (self.directory / "missing", link, self.directory):
            with self.subTest(path=path.name), self.assertRaises(GatewayError):
                load_routes(path)
        with patch("runtime.oci_gateway_config.os.geteuid", return_value=os.geteuid() + 1):
            with self.assertRaises(GatewayError):
                load_routes(self.path)

    def test_shared_permissions_oversize_malformed_and_duplicate_keys_fail(self):
        self.path.chmod(0o644)
        with self.assertRaises(GatewayError):
            load_routes(self.path)
        self.path.chmod(0o600)
        for body in ("x" * 32769, "{private-marker", '{"model_list":[],"model_list":[]}',
                     json.dumps(gateway_config()).replace('"num_retries": 0',
                                                         '"num_retries": 1,"num_retries": 0')):
            with self.subTest(body=body[:20]):
                self.path.write_text(body)
                with self.assertRaisesRegex(GatewayError, "^Native gateway configuration is invalid$"):
                    load_routes(self.path)

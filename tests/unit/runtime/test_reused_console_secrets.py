"""Saved provider IDs use the existing host-only CURRENT credential boundary."""

import base64
import json
import subprocess
import unittest
from unittest.mock import patch

from runtime.console_secrets import read_secret
from runtime.gateway_http import GatewayError
from .optional_console_fixture import settings


class ReusedConsoleSecretTests(unittest.TestCase):
    @patch("runtime.console_secrets.subprocess.run")
    def test_saved_keys_use_exact_ids_and_instance_identity(self, run):
        config = settings()
        config["provider_secrets"] = {
            "anthropic": "ocid1.vaultsecret.oc1.iad.sharedanthropic",
            "openai": "ocid1.vaultsecret.oc1.iad.sharedopenai",
        }
        for identifier in config["provider_secrets"].values():
            with self.subTest(identifier=identifier):
                run.return_value = subprocess.CompletedProcess([], 0, json.dumps({"data": {
                    "secret-id": identifier, "stages": ["CURRENT"], "version-number": 2,
                    "secret-bundle-content": {"content-type": "BASE64",
                                              "content": base64.b64encode(b"synthetic-key").decode()},
                }}), "")
                secret = read_secret(config, secret_id=identifier)
                self.assertEqual(secret.content, b"synthetic-key")
                self.assertNotIn("synthetic-key", repr(secret))
                command = run.call_args.args[0]
                for flag, value in (("--secret-id", identifier), ("--auth", "instance_principal"),
                                    ("--region", config["runtime"]["region"]), ("--stage", "CURRENT")):
                    self.assertEqual(command[command.index(flag) + 1], value)
                self.assertNotIn(config["vault_ocid"], command)
        run.reset_mock()
        with self.assertRaises(GatewayError):
            read_secret(config, secret_id="ocid1.vaultsecret.oc1.iad.unselected")
        run.assert_not_called()

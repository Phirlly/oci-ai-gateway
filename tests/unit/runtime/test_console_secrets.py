"""Direct secret reads are instance-authenticated, bounded and never print content."""

import base64
import json
import subprocess
import unittest
from unittest.mock import patch

from runtime.console_secrets import read_secret
from runtime.gateway_http import GatewayError
from .console_fixture import settings


class ConsoleSecretTests(unittest.TestCase):
    def response(self, **changes):
        data = {"secret-id": settings()["native"]["secret_ocid"], "stages": ["CURRENT"],
                "version-number": 2, "secret-bundle-content": {
                    "content-type": "BASE64", "content": base64.b64encode(b"synthetic-key").decode()}}
        data.update(changes)
        return subprocess.CompletedProcess([], 0, json.dumps({"data": data}), "")

    @patch("runtime.console_secrets.subprocess.run")
    def test_id_and_name_reads_use_current_instance_principal(self, run):
        run.return_value = self.response()
        value = read_secret(settings(), secret_id=settings()["native"]["secret_ocid"])
        self.assertEqual((value.content, value.version), (b"synthetic-key", 2))
        self.assertNotIn("synthetic-key", repr(value))
        command = run.call_args.args[0]
        self.assertIn("instance_principal", command)
        self.assertEqual(command[-2:], ["--stage", "CURRENT"])
        read_secret(settings(), context=True)
        command = run.call_args.args[0]
        self.assertIn("get-secret-bundle-by-name", command)
        self.assertIn(settings()["vault_ocid"], command)
        self.assertIn(settings()["context_name"], command)

    @patch("runtime.console_secrets.subprocess.run")
    def test_mismatched_id_noncurrent_and_failed_reads_are_sanitized(self, run):
        for result in (self.response(**{"secret-id": "ocid1.vaultsecret.oc1.iad.other"}),
                       self.response(stages=["PENDING"]), self.response(**{"version-number": True}),
                       subprocess.CompletedProcess([], 1, "synthetic-secret", "synthetic-secret")):
            run.return_value = result
            with self.assertRaises(GatewayError) as error:
                read_secret(settings(), secret_id=settings()["native"]["secret_ocid"])
            self.assertNotIn("synthetic-secret", str(error.exception))

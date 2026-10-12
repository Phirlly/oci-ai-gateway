"""Readiness retries network errors, preserves TLS trust and closes sockets."""

import os
import socket
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from orm.vault_readiness import probe, tls_context

HOST = "example-management.kms.us-ashburn-1.oraclecloud.com"


class VaultProbeTests(unittest.TestCase):
    def test_default_trust_does_not_enable_ambient_key_logging(self):
        with tempfile.TemporaryDirectory() as directory:
            keylog = Path(directory) / "unwanted.keys"
            with patch.dict(os.environ, {"SSLKEYLOGFILE": str(keylog)}):
                context = tls_context()
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            self.assertIsNone(context.keylog_filename)
            self.assertFalse(keylog.exists())

    def test_dns_then_connection_failure_retry_before_verified_tls(self):
        connection, context = MagicMock(), MagicMock()
        with patch("orm.vault_readiness.socket.create_connection", side_effect=[
            socket.gaierror("private detail"), ConnectionRefusedError(), connection,
        ]) as connect, patch("orm.vault_readiness.tls_context", return_value=context), \
                patch("orm.vault_readiness.time.sleep") as sleep:
            probe(HOST, budget=2)
        self.assertEqual(connect.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(connect.call_args.args, ((HOST, 443),))
        context.wrap_socket.assert_called_once_with(connection.__enter__.return_value, server_hostname=HOST)
        connection.__exit__.assert_called_once()
        context.wrap_socket.return_value.__exit__.assert_called_once()

    def test_certificate_and_protocol_failures_stop_without_retry(self):
        for error in (ssl.SSLCertVerificationError("private detail"), ssl.SSLError("private detail")):
            connection, context = MagicMock(), MagicMock()
            context.wrap_socket.side_effect = error
            with patch("orm.vault_readiness.socket.create_connection", return_value=connection), \
                    patch("orm.vault_readiness.tls_context", return_value=context), \
                    patch("orm.vault_readiness.time.sleep") as sleep:
                with self.assertRaises(ssl.SSLError):
                    probe(HOST, budget=2)
            sleep.assert_not_called()
            connection.__exit__.assert_called_once()

"""The actual probe exits during blocked native DNS/TLS and cancellation."""

import os
import signal
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures/vault_readiness.py"
SCRIPT = Path(__file__).resolve().parents[3] / "orm/vault_readiness.py"


class VaultDeadlineContracts(unittest.TestCase):
    def test_native_block_and_inherited_alarm_mask_cannot_defeat_deadline(self):
        for mode in ("native", "inherited"):
            with self.subTest(mode=mode):
                started = time.monotonic()
                result = subprocess.run([sys.executable, "-I", "-B", str(FIXTURE), mode],
                                        capture_output=True, text=True, timeout=4)
                self.assertEqual(result.returncode, -signal.SIGALRM, result.stderr)
                self.assertIn("BLOCKED_RESOLVER", result.stdout)
                self.assertLess(time.monotonic() - started, 3)

    def test_tls_stall_and_forced_cancellation_close_the_socket(self):
        for mode in ("tls", "cancel"):
            with self.subTest(mode=mode), socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                listener.settimeout(4)
                with subprocess.Popen([sys.executable, "-I", "-B", str(FIXTURE), mode,
                                       str(listener.getsockname()[1])],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                    try:
                        connection, _ = listener.accept()
                        with connection:
                            connection.settimeout(4)
                            self.assertTrue(connection.recv(8192), "Expected actual TLS ClientHello")
                            if mode == "cancel":
                                process.kill()  # Terraform CommandContext can force-stop local-exec.
                            _, error = process.communicate(timeout=4)
                            self.assertEqual(process.returncode,
                                             -signal.SIGKILL if mode == "cancel" else -signal.SIGALRM, error)
                            self.assertEqual(connection.recv(8192), b"")
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait(timeout=4)

    def test_invalid_input_exits_without_echoing_environment_or_endpoint(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT)], capture_output=True,
                                text=True, timeout=4, env={**os.environ,
                                    "VAULT_READINESS_ENDPOINT": "https://secret-sentinel.invalid",
                                    "VAULT_READINESS_REGION": "us-ashburn-1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("secret-sentinel", result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

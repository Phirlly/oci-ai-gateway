"""Only systemd's private listener is accepted; worker exit preserves it."""

import os
import select
import socket
import sys
import unittest
from types import SimpleNamespace

from runtime.oci_signing_protocol import Deadline, send_frame
from .manager_fixture import manager
from tests.unit.runtime.oci_signing_fixture import chat_body


@unittest.skipUnless(sys.platform == "linux", "Production activation requires Linux SO_ACCEPTCONN")
class ActivationContracts(unittest.TestCase):
    def test_restart_retains_listener_path_flags_and_accepts_new_requests(self):
        with manager() as owner:
            inode = os.stat(owner.path).st_ino
            for _ in range(2):
                worker = owner.start()
                client = owner.client()
                request = SimpleNamespace(method="POST", url=client.scope.url,
                                          body=chat_body(), headers={})
                client.do_request_sign(request)
                self.assertEqual(request.headers["authorization"], "Signature synthetic-1")
                stdout, stderr = owner.stop(worker)
                self.assertEqual(worker.returncode, 0)
                self.assertEqual((stdout, stderr), (b"", b""))
                self.assertEqual(os.stat(owner.path).st_ino, inode)
                self.assertFalse(os.get_blocking(owner.listener.fileno()))

    def test_missing_wrong_pid_count_and_name_reject_activation(self):
        for mode in ("bad-pid", "bad-count", "bad-name", "bad-missing", "closed-fd",
                     "inet-fd", "not-listening", "wrong-owner"):
            with self.subTest(mode=mode), manager() as owner:
                worker = owner.start(mode, ready=False)
                stdout, stderr = worker.communicate(timeout=5)
                self.assertEqual(worker.returncode, 1)
                self.assertEqual(stdout, b"")
                self.assertEqual(stderr, b"Signing worker unavailable\n")
                self.assertTrue(os.path.exists(owner.path))

    def test_blocking_manager_descriptor_is_rejected_without_changing_flags(self):
        with manager() as owner:
            owner.listener.setblocking(True)
            worker = owner.start(ready=False)
            worker.communicate(timeout=5)
            self.assertEqual(worker.returncode, 1)
            self.assertTrue(os.get_blocking(owner.listener.fileno()))

    def test_stop_during_signing_closes_connection_but_preserves_listener(self):
        with manager() as owner:
            worker = owner.start("slow")
            with owner.connection() as connection:
                send_frame(connection, chat_body(), Deadline(1), 262144)
                connection.shutdown(socket.SHUT_WR)
                self.assertTrue(select.select([worker.stdout], [], [], 2)[0])
                self.assertEqual(worker.stdout.readline(), b"signing\n")
                owner.stop(worker)
                self.assertEqual(worker.returncode, 0)
                self.assertEqual(connection.recv(1), b"")
            owner.start()
            client = owner.client()
            request = SimpleNamespace(method="POST", url=client.scope.url, body=chat_body(), headers={})
            client.do_request_sign(request)
            self.assertEqual(request.headers["authorization"], "Signature synthetic-1")

    def test_public_socket_or_parent_directory_is_rejected(self):
        for parent in (False, True):
            with self.subTest(parent=parent), manager() as owner:
                os.chmod(os.path.dirname(owner.path) if parent else owner.path, 0o755 if parent else 0o666)
                worker = owner.start(ready=False)
                worker.communicate(timeout=5)
                self.assertEqual(worker.returncode, 1)

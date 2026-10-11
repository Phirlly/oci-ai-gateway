"""Server authorization, bounded framing and fatal identity failure ownership."""

import json
import os
import socket
import struct
import sys
import time
import unittest

from runtime.oci_signing_protocol import Deadline, receive_frame, send_frame
from .manager_fixture import manager
from tests.unit.runtime.oci_signing_fixture import chat_body


def request(owner, body):
    with owner.connection() as connection:
        send_frame(connection, body, Deadline(1), 256 * 1024)
        connection.shutdown(socket.SHUT_WR)
        return json.loads(receive_frame(connection, Deadline(1), 65536))


@unittest.skipUnless(sys.platform == "linux", "Production activation requires Linux SO_ACCEPTCONN")
class SigningServiceContracts(unittest.TestCase):
    def test_foreign_model_rejected_without_signing_then_valid_request_succeeds(self):
        with manager() as owner:
            owner.start()
            reply = request(owner, chat_body(servingMode={"servingType": "ON_DEMAND", "modelId": "foreign"}))
            self.assertEqual(reply, {"status": "rejected"})
            reply = request(owner, chat_body())
            self.assertEqual(reply["headers"]["authorization"], "Signature synthetic-1")

    def test_malformed_frames_close_and_leave_worker_usable(self):
        with manager() as owner:
            worker = owner.start()
            for wire in (struct.pack("!I", 262145), struct.pack("!I", 2) + b"a",
                         struct.pack("!I", 1) + b"ab", b"\x00"):
                with self.subTest(wire=wire), owner.connection() as connection:
                    connection.sendall(wire)
                    connection.shutdown(socket.SHUT_WR)
                    try:
                        self.assertEqual(connection.recv(1), b"")
                    except ConnectionResetError:
                        pass  # Closing a socket with unread input can reset it.
            self.assertIsNone(worker.poll())
            self.assertEqual(request(owner, chat_body())["status"], "ok")

    def test_trickling_request_cannot_extend_receive_budget(self):
        with manager() as owner:
            owner.start()
            started = time.monotonic()
            with owner.connection() as connection:
                connection.sendall(struct.pack("!I", 100))
                for _ in range(10):
                    try:
                        connection.sendall(b"a")
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    time.sleep(0.05)
                else:
                    self.fail("Trickling request outlived total deadline")
            self.assertLess(time.monotonic() - started, 0.8)
            self.assertEqual(request(owner, chat_body())["status"], "ok")

    def test_fatal_identity_error_is_sanitized_and_worker_exits(self):
        with manager() as owner:
            worker = owner.start("fatal")
            self.assertEqual(request(owner, chat_body()), {"status": "unavailable"})
            stdout, stderr = worker.communicate(timeout=3)
            self.assertEqual(worker.returncode, 1)
            self.assertEqual((stdout, stderr), (b"", b""))

    def test_fatal_failure_exits_even_if_peer_cannot_receive_reply(self):
        with manager() as owner:
            worker = owner.start("fatal")
            with owner.connection() as connection:
                send_frame(connection, chat_body(), Deadline(1), 262144)
                connection.shutdown(socket.SHUT_WR)
            worker.communicate(timeout=3)
            self.assertEqual(worker.returncode, 1)
            self.assertTrue(os.path.exists(owner.path))

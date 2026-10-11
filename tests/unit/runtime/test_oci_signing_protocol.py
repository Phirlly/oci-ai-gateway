"""Bounded private frames reject ambiguity before a signer can run."""

import socket
import struct
import unittest

from runtime.oci_signing_protocol import Deadline, ProtocolError, receive_frame, send_frame


class SigningFrameTests(unittest.TestCase):
    def setUp(self):
        self.sender, self.receiver = socket.socketpair()
        self.addCleanup(self.sender.close)
        self.addCleanup(self.receiver.close)

    def test_binary_body_round_trips_without_reserialization(self):
        body = b' {"text": "different spacing"} \n'
        send_frame(self.sender, body, Deadline(1), 100)
        self.sender.shutdown(socket.SHUT_WR)
        self.assertEqual(receive_frame(self.receiver, Deadline(1), 100), body)

    def test_oversized_length_rejected_without_waiting_for_body(self):
        self.sender.sendall(struct.pack("!I", 101))
        with self.assertRaises(ProtocolError):
            receive_frame(self.receiver, Deadline(1), 100)

    def test_extra_frame_or_truncated_body_is_rejected(self):
        for wire in (struct.pack("!I", 1) + b"ab", struct.pack("!I", 2) + b"a",
                     b"\x00", struct.pack("!I", 0)):
            with self.subTest(wire=wire):
                sender, receiver = socket.socketpair()
                with sender, receiver:
                    sender.sendall(wire)
                    sender.shutdown(socket.SHUT_WR)
                    with self.assertRaises(ProtocolError):
                        receive_frame(receiver, Deadline(1), 100)

    def test_expired_total_budget_rejects_even_ready_data(self):
        self.sender.sendall(struct.pack("!I", 1) + b"a")
        self.sender.shutdown(socket.SHUT_WR)
        with self.assertRaises(ProtocolError):
            receive_frame(self.receiver, Deadline(0), 100)

    def test_send_rejects_non_bytes_empty_and_oversized_payload(self):
        for body in ("text", b"", b"a" * 101):
            with self.subTest(body=body), self.assertRaises(ProtocolError):
                send_frame(self.sender, body, Deadline(1), 100)

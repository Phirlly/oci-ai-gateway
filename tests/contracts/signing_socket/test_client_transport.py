"""Real socket reads remain bounded through partial replies and missing EOF."""

import select
import socket
import struct
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from runtime.gateway_http import GatewayError
from runtime.oci_signing_protocol import Deadline, receive_frame
from .manager_fixture import manager
from tests.unit.runtime.oci_signing_fixture import chat_body


def respond(owner, wire, *, trickle=False, delay_close=False):
    if not select.select([owner.listener], [], [], 2)[0]:
        raise AssertionError("Client never connected")
    with owner.listener.accept()[0] as connection:
        body = receive_frame(connection, Deadline(2), 262144)
        if body != chat_body():
            raise AssertionError("Transport changed request bytes")
        try:
            if trickle:
                for value in wire:
                    connection.sendall(bytes([value]))
                    time.sleep(0.06)
            else:
                connection.sendall(wire)
            if delay_close:
                time.sleep(0.4)
        except (BrokenPipeError, ConnectionResetError):
            pass


class ClientTransportContracts(unittest.TestCase):
    def call(self, client):
        request = SimpleNamespace(method="POST", url=client.scope.url, body=chat_body(), headers={})
        with self.assertRaisesRegex(GatewayError, "^Native signing unavailable$"):
            client.do_request_sign(request)
        self.assertEqual(request.headers, {})

    def test_trickling_reply_and_missing_eof_cannot_extend_total_budget(self):
        body = b'{"status":"unavailable"}'
        wire = struct.pack("!I", len(body)) + body
        for trickle in (True, False):
            with self.subTest(trickle=trickle), manager() as owner, ThreadPoolExecutor(1) as executor:
                future = executor.submit(respond, owner, wire, trickle=trickle, delay_close=not trickle)
                client = owner.client()
                client.timeout = 0.2
                started = time.monotonic()
                self.call(client)
                self.assertLess(time.monotonic() - started, 0.7)
                future.result(timeout=2)

    def test_oversized_truncated_and_trailing_replies_fail_closed(self):
        for wire in (struct.pack("!I", 65537), struct.pack("!I", 3) + b"a",
                     struct.pack("!I", 2) + b"{}extra", b"\x00"):
            with self.subTest(wire=wire), manager() as owner, ThreadPoolExecutor(1) as executor:
                future = executor.submit(respond, owner, wire)
                self.call(owner.client())
                future.result(timeout=2)

    def test_absent_socket_fails_with_sanitized_error(self):
        with manager() as owner:
            client = owner.client()
            client.path += "-missing"
            self.call(client)

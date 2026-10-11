"""One bounded request/reply per private connection, with total time budgets."""

import json
import socket
import struct
import time

from .gateway_http import GatewayError
from .oci_signing_scope import MAX_SIGNING_BODY

SIGNING_SOCKET = "/run/oci-ai-gateway-signing/sign.sock"
MAX_REPLY = 65536


class ProtocolError(GatewayError):
    """Malformed, disconnected or expired private transport."""


class Deadline:
    def __init__(self, seconds):
        self.end = time.monotonic() + seconds

    def remaining(self):
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise ProtocolError("Native signing transport expired")
        return remaining


def _read(connection, length, deadline):
    chunks = bytearray()
    while len(chunks) < length:
        connection.settimeout(deadline.remaining())
        part = connection.recv(length - len(chunks))
        if not part:
            raise ProtocolError("Incomplete native signing frame")
        chunks.extend(part)
    return bytes(chunks)


def receive_frame(connection, deadline, maximum):
    try:
        length = struct.unpack("!I", _read(connection, 4, deadline))[0]
        if not 0 < length <= maximum:
            raise ProtocolError("Invalid native signing frame size")
        body = _read(connection, length, deadline)
        connection.settimeout(deadline.remaining())
        if connection.recv(1):
            raise ProtocolError("Extra native signing frame data")
        return body
    except OSError:
        raise ProtocolError("Native signing transport unavailable") from None


def send_frame(connection, body, deadline, maximum):
    if type(body) is not bytes or not 0 < len(body) <= maximum:
        raise ProtocolError("Invalid native signing frame size")
    try:
        connection.settimeout(deadline.remaining())
        connection.sendall(struct.pack("!I", len(body)) + body)
    except OSError:
        raise ProtocolError("Native signing transport unavailable") from None


def exchange(path, body, *, timeout):
    deadline = Deadline(timeout)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(deadline.remaining())
            connection.connect(path)
            send_frame(connection, body, deadline, MAX_SIGNING_BODY)
            connection.shutdown(socket.SHUT_WR)
            return receive_frame(connection, deadline, MAX_REPLY)
    except OSError:
        raise ProtocolError("Native signing transport unavailable") from None


def decode_reply(content):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError
            value[key] = item
        return value
    if type(content) is not bytes or not 0 < len(content) <= MAX_REPLY:
        raise ValueError
    return json.loads(content.decode("utf-8"), object_pairs_hook=unique)

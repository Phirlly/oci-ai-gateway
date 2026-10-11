"""Serial host signer on a private systemd-owned Unix listening socket."""

import json
import os
import select
import socket
import stat
from pathlib import Path

from .gateway_http import GatewayError
from .oci_signing_protocol import Deadline, MAX_REPLY, ProtocolError, SIGNING_SOCKET, receive_frame, send_frame
from .oci_signing_scope import MAX_SIGNING_BODY, SigningRejected

ACTIVATION_ENV = ("LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES")


def activated_listener(path=SIGNING_SOCKET, *, expected_uid=0):
    values = tuple(os.environ.pop(name, None) for name in ACTIVATION_ENV)
    listener = None
    try:
        if values != (str(os.getpid()), "1", "signing"):
            raise ValueError
        listener = socket.socket(fileno=3)
        metadata, parent = Path(path).lstat(), Path(path).parent.lstat()
        if (listener.family != socket.AF_UNIX or listener.type != socket.SOCK_STREAM
                or listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) != 1
                or listener.getsockname() != str(path) or os.get_blocking(3)
                or not stat.S_ISSOCK(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
                or not stat.S_ISDIR(parent.st_mode) or stat.S_IMODE(parent.st_mode) != 0o700
                or metadata.st_uid != expected_uid or parent.st_uid != expected_uid):
            raise ValueError
        os.set_inheritable(3, False)
        return listener
    except (OSError, ValueError):
        if listener is not None:
            listener.close()  # Only this worker's copy; never unlink or shutdown.
        raise GatewayError("Private signing socket activation failed") from None


def _reply(connection, value, timeout):
    content = json.dumps(value, separators=(",", ":")).encode()
    send_frame(connection, content, Deadline(timeout), MAX_REPLY)


def serve(listener, signer, *, receive_timeout=5, reply_timeout=3):
    while True:
        # The manager shares listener flags: never change blocking or timeout.
        select.select([listener], [], [])
        try:
            connection, _ = listener.accept()
        except BlockingIOError:
            continue
        with connection:
            try:
                body = receive_frame(connection, Deadline(receive_timeout), MAX_SIGNING_BODY)
            except ProtocolError:
                continue
            fatal = False
            try:
                reply = {"status": "ok", "headers": signer.sign(body, timeout=20)}
            except SigningRejected:
                reply = {"status": "rejected"}
            except Exception:
                # No SDK exception, request or token may enter logs or the wire.
                fatal, reply = True, {"status": "unavailable"}
            try:
                _reply(connection, reply, reply_timeout)
            except ProtocolError:
                pass
            if fatal:
                return 1

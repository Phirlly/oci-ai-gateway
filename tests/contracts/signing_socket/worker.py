"""Emulate systemd's inherited descriptor in an isolated main-thread worker."""

import base64
import hashlib
import os
import signal
import socket
import sys
import time

from runtime.oci_instance_signer import SigningUnavailable
from runtime.oci_signing_scope import SigningScope
from runtime.oci_signing_service import activated_listener, serve
from runtime.oci_signing_entrypoint import _stop
from tests.unit.runtime.oci_signing_fixture import COMPARTMENT, MODEL, REGION


class SyntheticSigner:
    def __init__(self, mode):
        self.scope = SigningScope(REGION, COMPARTMENT, MODEL)
        self.mode, self.calls = mode, 0

    def sign(self, body, *, timeout):
        self.scope.validate(body)
        if self.mode == "fatal":
            raise SigningUnavailable("private-credential-marker")
        if self.mode == "slow":
            print("signing", flush=True)
            time.sleep(5)
        self.calls += 1
        return {"authorization": "Signature synthetic-" + str(self.calls),
                "date": "Sat, 10 Oct 2026 12:00:00 GMT", "host": self.scope.host,
                "content-type": "application/json", "content-length": str(len(body)),
                "x-content-sha256": base64.b64encode(hashlib.sha256(body).digest()).decode()}


def main():
    signal.signal(signal.SIGTERM, _stop)
    descriptor, path, mode = sys.argv[1:]
    descriptor = int(descriptor)
    if descriptor != 3:
        os.dup2(descriptor, 3)
        os.close(descriptor)
    os.environ.update(LISTEN_PID=str(os.getpid()), LISTEN_FDS="1", LISTEN_FDNAMES="signing")
    if mode in ("bad-pid", "bad-count", "bad-name", "bad-missing"):
        name, value = {"bad-pid": ("LISTEN_PID", "0"), "bad-count": ("LISTEN_FDS", "2"),
                       "bad-name": ("LISTEN_FDNAMES", "unexpected"),
                       "bad-missing": ("LISTEN_PID", "")}[mode]
        os.environ[name] = value
    if mode == "closed-fd":
        os.close(3)
    if mode in ("inet-fd", "not-listening"):
        with socket.socket(socket.AF_INET if mode == "inet-fd" else socket.AF_UNIX) as replacement:
            os.dup2(replacement.fileno(), 3)
    try:
        with activated_listener(path, expected_uid=os.geteuid() + (mode == "wrong-owner")) as listener:
            if any(name in os.environ for name in ("LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES")):
                return 3
            if os.get_inheritable(listener.fileno()) or os.get_blocking(listener.fileno()):
                return 3
            print("ready", flush=True)
            return serve(listener, SyntheticSigner(mode), receive_timeout=0.2, reply_timeout=0.2)
    except Exception:
        print("Signing worker unavailable", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

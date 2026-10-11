"""Parent retains the Unix listener while replaceable service workers run."""

import os
import select
import socket
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from runtime.oci_signing_client import SocketSigner
from runtime.oci_signing_scope import SigningScope
from tests.unit.runtime.oci_signing_fixture import COMPARTMENT, MODEL, REGION

ROOT = Path(__file__).resolve().parents[3]


class SocketManager:
    def __init__(self, path, listener):
        self.path, self.listener, self.workers = path, listener, []

    def start(self, mode="normal", *, ready=True):
        process = subprocess.Popen(
            [sys.executable, "-m", "tests.contracts.signing_socket.worker",
             str(self.listener.fileno()), self.path, mode], cwd=ROOT,
            env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"},
            pass_fds=(self.listener.fileno(),), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.workers.append(process)
        if ready:
            readable, _, _ = select.select([process.stdout], [], [], 5)
            if not readable or process.stdout.readline() != b"ready\n":
                raise AssertionError("Signing worker failed to become ready")
        return process

    def client(self):
        return SocketSigner(SigningScope(REGION, COMPARTMENT, MODEL), path=self.path, timeout=1)

    def connection(self):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(2)
        connection.connect(self.path)
        return connection

    def stop(self, process):
        if process.poll() is None:
            process.terminate()
        try:
            return process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=3)
            raise AssertionError("Signing worker did not stop") from None


@contextmanager
def manager():
    # Keep AF_UNIX path below macOS's 104-byte limit as well as Linux's limit.
    with tempfile.TemporaryDirectory(prefix="sign-", dir="/tmp") as directory:
        path = str(Path(directory) / "sign.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(path)
            os.chmod(path, 0o600)
            listener.listen(3)
            listener.setblocking(False)
            owner = SocketManager(path, listener)
            try:
                yield owner
            finally:
                for process in owner.workers:
                    if process.stdout.closed:
                        continue
                    owner.stop(process)

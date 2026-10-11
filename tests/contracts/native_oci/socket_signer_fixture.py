"""Production socket client against a bounded synthetic Unix responder."""

import asyncio
import base64
import hashlib
import json
import socket
import tempfile
import threading
from pathlib import Path

from runtime.oci_signing_client import SocketSigner
from runtime.oci_signing_protocol import Deadline, receive_frame, send_frame
from runtime.oci_signing_scope import SigningScope
from payload_fixture import COMPARTMENT, MODEL
from native_proxy_fixture import NativeProxyCase

SIGNATURE_MARKER = "synthetic-private-signing-token-marker"
PRIVATE_MARKER = "synthetic-private-signing-error-marker"


class UnixResponder:
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="native-sign-", dir="/tmp")
        self.path = str(Path(self.directory.name) / "sign.sock")
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(self.path)
        self.listener.listen(3)
        self.listener.settimeout(0.1)
        self.stop, self.received, self.release, self.completed = (threading.Event() for _ in range(4))
        self.release.set()
        self.requests, self.failures, self.mode = [], [], "ok"
        self.scope = SigningScope("us-ashburn-1", COMPARTMENT, MODEL)
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def reply(self, body):
        self.scope.validate(body)
        if self.mode != "ok":
            return (b"malformed " + PRIVATE_MARKER.encode() if self.mode == "malformed" else
                    json.dumps({"status": "unavailable", "detail": PRIVATE_MARKER}).encode())
        headers = {"authorization": 'Signature keyId="' + SIGNATURE_MARKER + '",signature="synthetic"',
                   "date": "Sat, 10 Oct 2026 12:00:00 GMT", "host": self.scope.host,
                   "content-type": "application/json", "content-length": str(len(body)),
                   "x-content-sha256": base64.b64encode(hashlib.sha256(body).digest()).decode()}
        return json.dumps({"status": "ok", "headers": headers}).encode()

    def run(self):
        while not self.stop.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                if not self.stop.is_set():
                    self.failures.append("listener failed")
                return
            try:
                with connection:
                    body = receive_frame(connection, Deadline(1), 262144)
                    self.requests.append(body)
                    self.received.set()
                    if not self.release.wait(2):
                        raise AssertionError("Signing reply was never released")
                    send_frame(connection, self.reply(body), Deadline(1), 65536)
            except Exception as error:
                self.failures.append(type(error).__name__)
            finally:
                self.completed.set()

    def close(self):
        self.release.set()
        self.stop.set()
        self.listener.close()
        self.thread.join(3)
        self.directory.cleanup()
        if self.thread.is_alive():
            raise AssertionError("Unix responder thread remains")
        if self.failures:
            raise AssertionError("Unix responder failed: " + ",".join(self.failures))


class ObservedSocketSigner(SocketSigner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.completed = threading.Event()

    def do_request_sign(self, request, enforce_content_headers=True):
        try:
            return super().do_request_sign(request, enforce_content_headers)
        finally:
            self.completed.set()


class SocketProxyCase(NativeProxyCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.socket = UnixResponder()
        self.addAsyncCleanup(asyncio.to_thread, self.socket.close)
        self.probe.oci_signer = ObservedSocketSigner(self.socket.scope, path=self.socket.path, timeout=1)

    async def wait_received(self):
        self.assertTrue(await asyncio.to_thread(self.socket.received.wait, 1), "signing never started")

    async def release_signer(self):
        self.socket.release.set()
        self.assertTrue(await asyncio.to_thread(self.socket.completed.wait, 1), "signing never completed")
        self.assertTrue(await asyncio.to_thread(self.probe.oci_signer.completed.wait, 1), "client signing remains")
        await asyncio.sleep(0.1)
        self.assertEqual(self.socket.failures, [])

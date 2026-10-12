"""Inject blocking only at production probe boundaries; never contact OCI."""

import ctypes
import importlib.util
import signal
import socket
import sys
from pathlib import Path

source = Path(__file__).resolve().parents[4] / "orm/vault_readiness.py"
spec = importlib.util.spec_from_file_location("vault_readiness", source)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
mode = sys.argv[1]

if mode in ("native", "inherited"):
    if mode == "inherited":
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})

    def blocked_resolver(*args, **kwargs):
        print("BLOCKED_RESOLVER", flush=True)
        # PyDLL holds the GIL; no Python exception handler can run here.
        ctypes.PyDLL(None).sleep(30)
        raise AssertionError("The production alarm did not stop the native call")

    probe.socket.getaddrinfo = blocked_resolver
else:
    port = int(sys.argv[2])
    original_connect = socket.create_connection
    probe.socket.create_connection = lambda address, **kwargs: original_connect(
        ("127.0.0.1", port), **kwargs)

probe.probe("example-management.kms.us-ashburn-1.oraclecloud.com", budget=0.4 if mode != "cancel" else 10)
raise AssertionError("A stalled probe cannot succeed")

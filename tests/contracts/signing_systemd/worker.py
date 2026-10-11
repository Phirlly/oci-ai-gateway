"""Synthetic signer using the actual systemd activation environment unchanged."""

import signal
import sys

from runtime.oci_signing_entrypoint import _stop
from runtime.oci_signing_service import activated_listener, serve
from tests.contracts.signing_socket.worker import SyntheticSigner


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _stop)
    with activated_listener(sys.argv[1]) as listener:
        sys.exit(serve(listener, SyntheticSigner("normal")))

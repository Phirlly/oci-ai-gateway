"""Run pinned Console contracts with owned cleanup and no provider access."""

import signal
import sys

from tests.contracts.runtime.__main__ import interrupted
from .credentials import CredentialActivation
from .edge import StatusEdge


def main():
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with StatusEdge() as edge:
            edge.check()
        print("Independent status and atomic publication passed.", flush=True)
        with CredentialActivation() as gateway:
            gateway.start()
            gateway.check_refresh()
        print("Mounted provider key refresh and database preservation passed.", flush=True)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"Console contract failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

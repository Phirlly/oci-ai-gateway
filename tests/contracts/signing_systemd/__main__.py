"""Run isolated real-manager contracts; never restart the shared Docker daemon."""

import unittest
import signal
import sys

from tests.contracts.runtime.__main__ import interrupted


def main():
    signal.signal(signal.SIGTERM, interrupted)
    try:
        result = unittest.main(module="tests.contracts.signing_systemd.test_activation", verbosity=2, exit=False)
        return 0 if result.result.wasSuccessful() else 1
    except KeyboardInterrupt:
        print("Systemd contract interrupted; owned cleanup attempted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

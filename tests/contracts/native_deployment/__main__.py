"""Check production native startup without OCI, provider keys or live inference."""

import signal
import sys

from tests.contracts.runtime.__main__ import interrupted
from .stack import NativeStack


def main():
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with NativeStack() as stack:
            stack.start()
            stack.check_startup()
            print("Production native startup, route policy and authentication checks passed.")
            return 0
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"Native startup verification failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

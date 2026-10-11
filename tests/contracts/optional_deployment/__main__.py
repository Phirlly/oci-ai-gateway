"""External-only production startup; disposable containers, no real API keys."""

import signal
import sys

from tests.contracts.runtime.__main__ import interrupted
from .stack import ExternalStack


def main():
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with ExternalStack() as stack:
            stack.start()
            stack.check_startup()
        print("External-only startup, route policy and authentication checks passed.")
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"External-only startup verification failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

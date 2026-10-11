"""Prepare the reviewed overlay, run native contracts, clean owned resources."""

import json
import signal
import sys
import tempfile
from pathlib import Path

from runtime.oci_adapter_overlay import IMAGE_MODULE_ROOT, prepare_overlay
from tests.contracts.runtime.__main__ import interrupted
from .container import prepare_engine, run_container


def main():
    signal.signal(signal.SIGTERM, interrupted)
    try:
        prepare_engine()
        exported = run_container(["-m", "runtime.oci_adapter_overlay"])
        if exported.returncode:
            raise RuntimeError("Pinned native source export failed")
        results = prepare_overlay(json.loads(exported.stdout))
        with tempfile.TemporaryDirectory(prefix="gateway-native-contract-") as directory:
            mounts = []
            for name, body in results.items():
                path = Path(directory) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
                mounts.append((path, IMAGE_MODULE_ROOT + "/" + name))
            result = run_container(["-m", "unittest", "discover", "-s", "/checks", "-v"], mounts)
            print(result.stderr[-16000:], end="", file=sys.stderr)
            return result.returncode
    except KeyboardInterrupt:
        print("Native contracts interrupted; owned-resource cleanup attempted", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Native contracts failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

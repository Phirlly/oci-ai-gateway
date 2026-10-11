"""Dedicated root service entrypoint; configuration never supplies credentials."""

import json
import os
import signal
import stat
import sys
from pathlib import Path

from .gateway_http import GatewayError
from .oci_instance_signer import InstanceSigner
from .oci_signing_scope import SigningScope
from .oci_signing_service import activated_listener, serve
from .runtime_bundle import validate_settings


def load_settings(path=Path("/etc/oci-ai-gateway.json"), *, expected_uid=0):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError
            value[key] = item
        return value
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != expected_uid
                    or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_size > 8192):
                raise ValueError
            content = stream.read(8193)
            if len(content) > 8192:
                raise ValueError
        return validate_settings(json.loads(content, object_pairs_hook=unique))
    except (OSError, ValueError, TypeError, RecursionError):
        raise GatewayError("Private signing settings could not be verified") from None


def _stop(signum, frame):
    raise SystemExit(0)


def main():
    try:
        if os.geteuid() != 0:
            raise GatewayError("Signing service requires root")
        signal.signal(signal.SIGTERM, _stop)
        settings = load_settings()
        model_id = settings["models"]["oci"] if settings["schema_version"] == 4 else settings["model_id"]
        scope = SigningScope(settings["inference_region"], settings["compartment_ocid"], model_id)
        signer = InstanceSigner(scope, settings["tenancy_ocid"], settings["region"])
        with activated_listener() as listener:
            return serve(listener, signer)
    except Exception:
        print("Native signing service unavailable", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

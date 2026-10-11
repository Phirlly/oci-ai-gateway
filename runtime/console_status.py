"""Publish fixed public status categories; never publish an exception or model body."""

import json
import os
import stat
import tempfile
from pathlib import Path

from .gateway_http import GatewayError

MESSAGES = {
    "PREPARING": "Preparing the gateway.",
    "WAITING_CREDENTIALS": "Save each enabled provider's key as its CURRENT plain-text secret version.",
    "WAITING_FRONTEND": "Waiting for trusted public HTTPS and presenter login; confirm the presenter secret contains the current password.",
    "VERIFYING": "Checking HTTPS, presenter access and samples for the enabled models.",
    "READY": "Last verification passed. Open Compare with the presenter credentials.",
    "FAILED": "One or more samples failed. Check model access, then increase verification_run and Apply.",
    "ERROR": "Setup or verification failed. Check secret contents and service logs; no secrets are shown here.",
    "INTERRUPTED": "Verification was interrupted. Increase verification_run and Apply to retry explicitly.",
}


def publish_status(directory, phase, record):
    temporary = None
    try:
        directory = Path(directory)
        directory.mkdir(mode=0o755, exist_ok=True)
        metadata = directory.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022:
            raise ValueError
        os.chmod(directory, 0o755)
        value = {"status": phase, "message": MESSAGES[phase], "verification_run": record["run"],
                 "samples_passed": record["passed"], "samples_total": record.get("total", 8),
                 "finished_at": record["finished_at"], "meaning": "Last verification result; not continuous health"}
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write((json.dumps(value, sort_keys=True, indent=2) + "\n").encode())
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
        os.replace(temporary, directory / "status.json")
        temporary = None
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except (OSError, ValueError, KeyError, TypeError):
        raise GatewayError("Public deployment status could not be updated") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

"""Root service entrypoint for direct Resource Manager deployments."""

import fcntl
import os
import stat
import sys
from contextlib import contextmanager
from pathlib import Path

from .console_runner import run_console
from .console_settings import decode_json, validate_console_settings
from .console_status import publish_status
from .console_state import read_record
from .gateway_http import GatewayError
from .host_commands import ensure_dependencies
from .host_firewall import protect_metadata

STATE = Path("/var/lib/oci-ai-gateway")
STATUS = Path("/var/lib/oci-ai-gateway-status")


def load_config(path=Path("/etc/oci-ai-gateway-console.json")):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0
                or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_size > 16384):
            raise GatewayError("Unsafe Console bootstrap settings")
        return validate_console_settings(decode_json(stream.read(16385)))


@contextmanager
def locked_state(directory):
    metadata = directory.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o077:
        raise GatewayError("Bootstrap directory must be private and root-owned")
    descriptor = os.open(directory / "bootstrap.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, "r+") as lock:
        metadata = os.fstat(lock.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o077:
            raise GatewayError("Unsafe bootstrap lock")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    try:
        if os.geteuid() != 0:
            raise GatewayError("Console bootstrap requires root")
        with locked_state(STATE):
            settings = load_config()
            saved = read_record(STATE, "console-state.json") if settings["schema_version"] == 2 else None
            if saved is None or saved.get("phase") == "preparing":
                ensure_dependencies()
            protect_metadata()
            run_console(settings, STATE, STATUS)
        return 0  # Timer remains enabled to observe explicit verification_run changes.
    except BlockingIOError:
        return 75  # Another serialized bootstrap owns publication.
    except (GatewayError, OSError, ValueError, TypeError, RecursionError):
        try:
            publish_status(STATUS, "ERROR", {"run": 0, "passed": 0, "finished_at": ""})
        except GatewayError:
            pass
        print("Console bootstrap could not verify its inputs or complete setup; timer will retry", file=sys.stderr)
        return 1

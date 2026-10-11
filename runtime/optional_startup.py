"""Install one immutable host guard before Docker can start on schema4 guests."""

import json
import os
import stat
from pathlib import Path

from .install_assets import install_assets
from .runtime_bundle import _unique, validate_settings

GUARD = ("[Service]\nEnvironment=PYTHONPATH=/opt/oci-ai-gateway\n"
         "ExecStartPre=/usr/bin/python3 -m runtime.host_firewall\n"
         "ExecStartPost=/usr/bin/python3 -m runtime.host_firewall\n")
NATIVE = "[Unit]\nRequires=oci-ai-gateway-signing.socket\nAfter=oci-ai-gateway-signing.socket\n\n"


def configure_host(settings, root=Path("/")):
    settings = validate_settings(settings)
    if settings["schema_version"] != 4:
        raise ValueError("Optional host package requires schema4 settings")
    native = "oci" in settings["models"]
    name = "runtime/systemd/docker-native.conf" if native else "runtime/systemd/docker-guard.conf"
    install_assets(json.dumps({name: (NATIVE if native else "") + GUARD}).encode(), root)


def prepare_host(path=Path("/etc/oci-ai-gateway.json")):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
                or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_size > 8192):
            raise ValueError("Unsafe runtime settings")
        settings = json.loads(stream.read(8193), object_pairs_hook=_unique)
    configure_host(settings)

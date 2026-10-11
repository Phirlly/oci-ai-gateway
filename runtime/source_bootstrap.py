"""Verify or fetch immutable runtime sources before importing the VM bootstrap."""

import json
import os
import stat
import sys
from hashlib import sha256
from pathlib import Path

from .install_assets import asset_destination, install_assets
from .gateway_http import GatewayError
from .source_archive import load_manifest, validate_manifest
from .source_download import download_sources


def installed_sources(manifest, root):
    values, missing = {}, False
    for name, checksum in manifest["files"].items():
        try:
            descriptor = os.open(root / asset_destination(name), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            missing = True
            continue
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
                    or metadata.st_mode & 0o022 or metadata.st_size > 65536):
                raise ValueError("Unsafe installed runtime source")
            content = stream.read(65537)
        if sha256(content).hexdigest() != checksum:
            raise ValueError("Installed runtime source differs from its deployment")
        values[name] = content.decode("utf-8")
    return None if missing else values


def prepare_sources(manifest, root=Path("/")):
    validate_manifest(manifest)
    values = installed_sources(manifest, root)
    if values is None:
        values = download_sources(manifest)
    install_assets(json.dumps(values, separators=(",", ":")).encode(), root)


def main(*, console=False):
    try:
        if os.geteuid() != 0:
            raise ValueError("Runtime source bootstrap requires root")
        descriptor = os.open("/etc/oci-ai-gateway-source.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o077:
                raise ValueError("Unsafe runtime source manifest")
            manifest = load_manifest(stream.read(16385))
        prepare_sources(manifest)
        if "runtime/optional_startup.py" in manifest["files"]:
            from .optional_startup import prepare_host
            prepare_host()
        from .host_commands import _run
        _run(["/usr/bin/systemctl", "daemon-reload"], "Downloaded service unit activation", 30)
        if console:
            from .console_bootstrap import main as bootstrap
        else:
            from .bootstrap import main as bootstrap
        return bootstrap()
    except (OSError, ValueError, TypeError, RecursionError, GatewayError):
        print("Runtime sources could not be verified; bootstrap timer will retry", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--console", action="store_true")
    sys.exit(main(console=parser.parse_args().console))

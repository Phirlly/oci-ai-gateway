"""Prepare two exact LiteLLM OCI source replacements; never activate them."""

import importlib.util
import json
import os
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path

IMAGE = "ghcr.io/berriai/litellm@sha256:625981c83410a3ea68eb0697590a57ec1d764d634514d54fa5db0591077ee839"
IMAGE_MODULE_ROOT = "/app/.venv/lib/python3.13/site-packages/litellm"
SOURCE_HASHES = {
    "llms/oci/chat/generic.py": "6ac690ab76287605f923fa62bdb2e20faf8f213db2d549972455ad67063c0e6e",
    "llms/oci/chat/transformation.py": "549c63e233d9717257a183c95ab42317cf44ac6945f341983c2bd22878d38d72",
}
RESULT_HASHES = {
    "llms/oci/chat/generic.py": "22e9b1bf9a986d94dd2460163b6a30eddc90b047dd1898f16daf70f586260a67",
    "llms/oci/chat/transformation.py": "4bba76a085e34c7938530436ac250d258511b0b28aeebad476b45bd273d697a7",
}
PATCH_PATH = Path(__file__).with_name("litellm_oci.patch")
PATCH_HASH = "3a7ff6bc704a8038e46fa746cd4389eb05309fc9277b127fd6770a8fa81b6679"


class OverlayError(Exception):
    """Preparation failed without publishing any source."""


def _validate_files(files, expected):
    if not isinstance(files, dict) or set(files) != set(expected):
        raise ValueError
    for name, checksum in expected.items():
        body = files[name]
        if not isinstance(body, str) or len(body) > 65536:
            raise ValueError
        encoded = body.encode("utf-8")
        if len(encoded) > 65536 or sha256(encoded).hexdigest() != checksum:
            raise ValueError


def prepare_overlay(record):
    """Return verified replacement text; callers own any later publication."""
    try:
        if (not isinstance(record, dict) or set(record) != {"root", "files"}
                or record["root"] != IMAGE_MODULE_ROOT):
            raise ValueError
        _validate_files(record["files"], SOURCE_HASHES)
        with PATCH_PATH.open("rb") as stream:
            change = stream.read(32769)
        if len(change) > 32768 or sha256(change).hexdigest() != PATCH_HASH:
            raise ValueError
        with tempfile.TemporaryDirectory(prefix="gateway-oci-overlay-") as directory:
            root = Path(directory)
            for name, body in record["files"].items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            environment = {
                "PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CEILING_DIRECTORIES": str(root.parent),
            }
            for options in (["--check"], []):
                subprocess.run(["git", "apply", "--whitespace=error", *options, "-"],
                               input=change, capture_output=True, check=True, timeout=15,
                               cwd=root, env=environment)
            results = {name: (root / name).read_text(encoding="utf-8") for name in SOURCE_HASHES}
            _validate_files(results, RESULT_HASHES)
            for name, body in results.items():
                compile(body, name, "exec")
            return results
    except (OSError, ValueError, TypeError, SyntaxError, subprocess.SubprocessError):
        raise OverlayError("Native OCI adapter preparation failed") from None


def export_sources():
    """Run inside the pinned image; export only the two verified original files."""
    try:
        specification = importlib.util.find_spec("litellm")
        root = Path(specification.origin).parent
        if str(root) != IMAGE_MODULE_ROOT:
            raise ValueError
        files = {}
        for name in SOURCE_HASHES:
            with (root / name).open("rb") as stream:
                files[name] = stream.read(65537).decode("utf-8")
        _validate_files(files, SOURCE_HASHES)
        return {"root": str(root), "files": files}
    except (OSError, ValueError, TypeError, AttributeError):
        raise OverlayError("Native OCI adapter source export failed") from None


if __name__ == "__main__":
    try:
        print(json.dumps(export_sources()))
    except OverlayError as error:
        raise SystemExit(str(error))

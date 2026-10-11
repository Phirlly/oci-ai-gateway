"""Bind native runtime sources to the workflow's immutable public commit."""

import argparse
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from hashlib import sha256

from runtime.source_archive import validate_manifest
from runtime.source_download import download_sources

from .credential_errors import DeliveryError
from .foundation_package import FoundationPackage, NATIVE_FILES

SOURCE_PATH = "runtime/source.json"
SOURCE_EXCLUSIONS = {"runtime/compose.cloud.yaml", "runtime/systemd/docker-guard.conf",
                     "runtime/systemd/oci-ai-gateway-bootstrap.service"}


class NativePackage(FoundationPackage):
    @classmethod
    def build(cls, directory, *, repository, commit):
        def source_manifest(contents):
            values = {"schema_version": 1, "repository": repository, "commit": commit,
                      "files": {name: sha256(data).hexdigest() for name, data in contents.items()
                                if name.startswith("runtime/") and name not in SOURCE_EXCLUSIONS}}
            validate_manifest(values)
            return {SOURCE_PATH: json.dumps(values, sort_keys=True, separators=(",", ":")).encode()}
        return cls._build(directory, NATIVE_FILES, generated=source_manifest)

    def verify_public_source(self):
        try:
            with zipfile.ZipFile(io.BytesIO(self.content)) as archive:
                manifest = json.loads(archive.read(SOURCE_PATH))
            download_sources(manifest)
        except ValueError:
            raise DeliveryError("Public runtime commit does not match this package; push the exact source before deploying.") from None


def prepare_local_source(root, repository, commit):
    """Offline preparation of the ignored manifest used by local Terraform checks."""
    package = NativePackage.build(root, repository=repository, commit=commit)
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        content = archive.read(SOURCE_PATH)
    destination = Path(root) / SOURCE_PATH
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA"))
    options = parser.parse_args()
    prepare_local_source(Path(__file__).resolve().parents[1], options.repository, options.commit)

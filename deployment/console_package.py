"""Prepare a standalone Console root with immutable, hashed runtime sources."""

import argparse
import io
import json
import os
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from runtime.install_assets import DEMO_ASSETS
from runtime.source_archive import load_manifest
from runtime.source_download import download_sources

from .foundation_package import NATIVE_FILES
from .native_package import SOURCE_EXCLUSIONS
from .package_sources import package_sources

ROOT_FILES = ("main.tf", "providers.tf", "variables.tf", "secrets.tf", "bootstrap.tf", "outputs.tf", "schema.yaml")
CONSOLE_FILES = (
    "console_bootstrap.py", "console_runner.py", "console_settings.py", "console_secrets.py",
    "console_state.py", "console_credentials.py", "console_status.py", "console_services.py",
    "compose.console.yaml", "systemd/oci-ai-gateway-console-bootstrap.service",
)
FILES = {**{name.replace("foundation/", "gateway/", 1): source for name, source in NATIVE_FILES.items()},
         **{name: "orm/" + name for name in ROOT_FILES},
         **{"runtime/" + name: "runtime/" + name for name in CONSOLE_FILES},
         **{name: name for name in sorted(DEMO_ASSETS)},
         ".terraform.lock.hcl": "infra/.terraform.lock.hcl"}


@dataclass(frozen=True, repr=False)
class ConsolePackage:
    content: bytes

    @classmethod
    def build(cls, directory, *, repository, commit):
        def generated(contents):
            original = contents["main.tf"]
            selection = b'source = "../infra"'
            if original.count(selection) != 1:
                raise ValueError("Console module source changed; inspect the portable rewrite")
            excluded = SOURCE_EXCLUSIONS | {"runtime/systemd/oci-ai-gateway-native-bootstrap.service"}
            manifest = {"schema_version": 1, "repository": repository, "commit": commit,
                        "files": {name: sha256(data).hexdigest() for name, data in contents.items()
                                  if name.startswith(("runtime/", "demo/")) and name not in excluded}}
            encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            load_manifest(encoded)
            assets = {name: contents[name].decode() for name in manifest["files"]}
            if len(json.dumps(assets).encode()) > 256 * 1024:
                raise ValueError("Installed assets exceed their budget")
            return {"source.json": encoded, "main.tf": original.replace(selection, b'source = "./gateway"')}
        return cls(package_sources(directory, FILES, generated=generated))

    def verify_public_source(self):
        with zipfile.ZipFile(io.BytesIO(self.content)) as archive:
            download_sources(load_manifest(archive.read("source.json")))


def prepare_local_source(root, repository, commit):
    package = ConsolePackage.build(root, repository=repository, commit=commit)
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        (Path(root) / "orm/source.json").write_bytes(archive.read("source.json"))
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-public-source", action="store_true")
    options = parser.parse_args()
    package = prepare_local_source(Path(__file__).resolve().parents[1], options.repository, options.commit)
    if options.verify_public_source:
        package.verify_public_source()
    if options.output:
        with options.output.open("xb") as stream:
            stream.write(package.content)

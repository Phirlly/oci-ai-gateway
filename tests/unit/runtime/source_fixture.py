"""Synthetic public-commit archive with a retained file manifest."""

import io
import zipfile
from hashlib import sha256

FILES = {"runtime/bootstrap.py": "synthetic bootstrap", "runtime/install_assets.py": "synthetic installer"}


def manifest(files=FILES):
    return {"schema_version": 1, "repository": "synthetic/gateway", "commit": "a" * 40,
            "files": {name: sha256(body.encode()).hexdigest() for name, body in files.items()}}


def archive(files=FILES, root="arbitrary-archive-root", *, compression=zipfile.ZIP_STORED):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as stream:
        for name, body in files.items():
            entry = zipfile.ZipInfo(root + "/" + name)
            entry.external_attr = 0o100644 << 16
            entry.compress_type = compression
            stream.writestr(entry, body)
    return data.getvalue()

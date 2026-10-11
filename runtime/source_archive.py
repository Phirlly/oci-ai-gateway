"""Validate public commit provenance and every required runtime ZIP member."""

import io
import json
import re
import stat
import zipfile
import zlib
from hashlib import sha256

from .install_assets import asset_destination

MAX_DOWNLOAD = 8 * 1024 * 1024


def validate_manifest(value):
    if (not isinstance(value, dict) or set(value) != {"schema_version", "repository", "commit", "files"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(value["repository"], str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}", value["repository"]) is None
            or not isinstance(value["commit"], str) or re.fullmatch(r"[a-f0-9]{40}", value["commit"]) is None
            or not isinstance(value["files"], dict) or not 1 <= len(value["files"]) <= 48):
        raise ValueError("Invalid runtime source manifest")
    destinations = set()
    for name, checksum in value["files"].items():
        destination = asset_destination(name)
        if (destination in destinations or not isinstance(checksum, str)
                or re.fullmatch(r"[a-f0-9]{64}", checksum) is None):
            raise ValueError("Invalid runtime source member")
        destinations.add(destination)
    return value


def load_manifest(content):
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("Duplicate manifest field")
            result[name] = value
        return result
    if not isinstance(content, bytes) or len(content) > 16384:
        raise ValueError("Invalid runtime source manifest")
    return validate_manifest(json.loads(content, object_pairs_hook=unique))


def source_files(content, manifest):
    validate_manifest(manifest)
    if not isinstance(content, bytes) or len(content) > MAX_DOWNLOAD:
        raise ValueError("Runtime archive exceeded its download budget")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 4096 or sum(entry.file_size for entry in entries) > 32 * 1024 * 1024:
                raise ValueError("Runtime archive exceeded its member budget")
            selected, seen, roots = {}, set(), set()
            for entry in entries:
                parts = entry.filename.rstrip("/").split("/")
                mode = stat.S_IFMT(entry.external_attr >> 16)
                if (entry.orig_filename != entry.filename or entry.filename in seen or entry.flag_bits & 1
                        or any(part in ("", ".", "..") for part in parts) or "\\" in entry.filename
                        or mode not in (0, stat.S_IFREG, stat.S_IFDIR)
                        or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ValueError("Unsafe runtime archive member")
                seen.add(entry.filename)
                roots.add(parts[0])
                name = "/".join(parts[1:])
                if name not in manifest["files"]:
                    continue
                if entry.is_dir() or mode == stat.S_IFDIR or entry.file_size > 65536:
                    raise ValueError("Invalid runtime source member")
                with archive.open(entry) as stream:
                    data = stream.read(65537)
                if len(data) != entry.file_size or sha256(data).hexdigest() != manifest["files"][name]:
                    raise ValueError("Runtime source does not match the deployment")
                selected[name] = data.decode("utf-8")
            if len(roots) != 1 or set(selected) != set(manifest["files"]):
                raise ValueError("Runtime source archive is incomplete")
            return selected
    except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError):
        raise ValueError("Invalid runtime source archive") from None

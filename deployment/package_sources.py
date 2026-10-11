"""Build deterministic ZIP bytes from an explicit, bounded source-file allowlist."""

import io
import os
import stat
import zipfile
from pathlib import Path

from .credential_errors import DeliveryError

MAX_MEMBER_BYTES = 256 * 1024


def package_sources(directory, files, *, generated=None):
    directory = Path(directory)
    stream = io.BytesIO()
    try:
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError
        contents = {}
        for member, name in files.items():
            parent = directory
            for component in Path(name).parts[:-1]:
                parent = parent / component
                if parent.is_symlink() or not parent.is_dir():
                    raise ValueError
            descriptor = os.open(directory / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError
                content = source.read(MAX_MEMBER_BYTES + 1)
            if len(content) > MAX_MEMBER_BYTES:
                raise ValueError
            contents[member] = content
        if generated is not None:
            contents.update(generated(contents))
        if sum(len(data) for data in contents.values()) > 1024 * 1024:
            raise ValueError
        with zipfile.ZipFile(stream, "w") as archive:
            for member, content in contents.items():
                if len(content) > MAX_MEMBER_BYTES:
                    raise ValueError
                info = zipfile.ZipInfo(member, (2020, 1, 1, 0, 0, 0))
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                archive.writestr(info, content)
        return stream.getvalue()
    except (OSError, ValueError):
        raise DeliveryError("Required Terraform source files could not be packaged.") from None

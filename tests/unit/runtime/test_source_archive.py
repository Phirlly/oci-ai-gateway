"""A commit archive must match every retained runtime hash before installation."""

import io
import unittest
import warnings
import zipfile

from runtime.source_archive import source_files, validate_manifest
from .source_fixture import FILES, archive, manifest


class SourceArchiveTests(unittest.TestCase):
    def test_root_name_and_unselected_safe_files_do_not_change_source_identity(self):
        for root in ("original", "renamed-repo"):
            self.assertEqual(source_files(archive(FILES | {"README.md": "docs"}, root), manifest()), FILES)

    def test_missing_or_changed_required_source_is_rejected(self):
        for files in ({"runtime/bootstrap.py": FILES["runtime/bootstrap.py"]},
                      FILES | {"runtime/bootstrap.py": "changed"}):
            with self.subTest(files=files), self.assertRaises(ValueError):
                source_files(archive(files), manifest())

    def test_duplicate_link_and_unsafe_entries_are_rejected(self):
        for kind in ("duplicate", "link", "escape", "absolute"):
            data = io.BytesIO(archive())
            with warnings.catch_warnings(), zipfile.ZipFile(data, "a") as stream:
                warnings.simplefilter("ignore", UserWarning)
                name = {"duplicate": "arbitrary-archive-root/runtime/bootstrap.py", "link": "root/link",
                        "escape": "root/../escape", "absolute": "/escape"}[kind]
                entry = zipfile.ZipInfo(name)
                entry.external_attr = (0o120777 if kind == "link" else 0o100644) << 16
                stream.writestr(entry, "bad")
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                source_files(data.getvalue(), manifest())

    def test_encrypted_member_is_rejected_without_trying_a_password(self):
        data = bytearray(archive())
        header = data.index(b"PK\x01\x02")
        data[header + 8] |= 1  # ZIP central-directory encrypted flag.
        with self.assertRaisesRegex(ValueError, "Unsafe runtime archive member"):
            source_files(bytes(data), manifest())

    def test_manifest_rejects_arbitrary_repository_revision_and_paths(self):
        for changes in ({"repository": "../other"}, {"commit": "dev"}, {"files": {"../outside": "a" * 64}},
                        {"files": {"runtime/bootstrap.py": "not-a-hash"}}, {"extra": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_manifest(manifest() | changes)

    def test_download_and_member_size_budgets_are_enforced(self):
        for data in (b"x" * (8 * 1024 * 1024 + 1), archive(FILES | {"runtime/bootstrap.py": "x" * 65537})):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                source_files(data, manifest())

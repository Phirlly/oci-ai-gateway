"""ZIP/manifest bounds and malformed compressed input fail before installation."""

import json
import struct
import unittest
import zipfile

from runtime.source_archive import load_manifest, source_files
from .source_fixture import FILES, archive, manifest


class SourceArchiveLimitsTests(unittest.TestCase):
    def test_deflated_archive_preserves_all_verified_source_bytes(self):
        self.assertEqual(source_files(archive(compression=zipfile.ZIP_DEFLATED), manifest()), FILES)

    def test_corrupt_deflate_is_a_sanitized_validation_error(self):
        data = bytearray(archive(compression=zipfile.ZIP_DEFLATED))
        name_length, extra_length = struct.unpack_from("<HH", data, 26)
        data[30 + name_length + extra_length] = 0x07  # Reserved DEFLATE block type.
        with self.assertRaisesRegex(ValueError, "Invalid runtime source archive"):
            source_files(bytes(data), manifest())

    def test_member_count_and_declared_total_size_are_bounded(self):
        many = archive(FILES | {"notes/" + str(i): "" for i in range(4095)})
        large = bytearray(archive())
        header = large.index(b"PK\x01\x02")
        struct.pack_into("<I", large, header + 24, 32 * 1024 * 1024 + 1)
        for data in (many, bytes(large)):
            with self.subTest(size=len(data)), self.assertRaisesRegex(ValueError, "member budget"):
                source_files(data, manifest())

    def test_duplicate_manifest_fields_and_members_are_rejected(self):
        record = json.dumps(manifest())
        member = json.dumps(next(iter(manifest()["files"])))
        duplicate_file = record.replace(member + ":", member + ': "' + "a" * 64 + '", ' + member + ":", 1)
        for content in ('{"schema_version": 1, ' + record[1:], duplicate_file):
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "Duplicate manifest field"):
                load_manifest(content.encode())

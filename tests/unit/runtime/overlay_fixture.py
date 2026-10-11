"""Small synthetic source files exercised through real Git application."""

import difflib
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import oci_adapter_overlay as overlay


def hashes(files):
    return {name: hashlib.sha256(body.encode()).hexdigest() for name, body in files.items()}


class OverlayCase(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.sources = {name: "value = 1\n" for name in overlay.SOURCE_HASHES}
        self.results = {name: "value = 2\n" for name in self.sources}
        self.record = {"root": overlay.IMAGE_MODULE_ROOT, "files": self.sources.copy()}
        self.change = self.directory / "candidate.patch"
        self.change.write_text("".join("".join(difflib.unified_diff(
            old.splitlines(True), self.results[name].splitlines(True),
            fromfile="a/" + name, tofile="b/" + name,
        )) for name, old in self.sources.items()))
        for name, value in (("SOURCE_HASHES", hashes(self.sources)),
                            ("RESULT_HASHES", hashes(self.results)),
                            ("PATCH_PATH", self.change),
                            ("PATCH_HASH", hashlib.sha256(self.change.read_bytes()).hexdigest())):
            self.enterContext(patch.object(overlay, name, value))
        self.temporary = []
        factory = tempfile.TemporaryDirectory

        def workspace(**options):
            result = factory(dir=self.directory, **options)
            self.temporary.append(Path(result.name))
            return result

        self.enterContext(patch.object(overlay.tempfile, "TemporaryDirectory", side_effect=workspace))

    def assert_clean(self):
        self.assertTrue(all(not path.exists() for path in self.temporary))
        self.assertEqual(set(self.directory.iterdir()), {self.change})

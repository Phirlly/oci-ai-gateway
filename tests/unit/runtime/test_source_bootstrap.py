"""Runtime source installation resumes locally and never replaces conflicting code."""

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from runtime.source_bootstrap import main, prepare_sources
from .source_fixture import FILES, manifest


class SourceBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.download = self.enterContext(patch("runtime.source_bootstrap.download_sources", return_value=FILES))

    def test_fresh_install_and_completed_resume_preserve_files_without_download(self):
        prepare_sources(manifest(), self.root)
        path = self.root / "opt/oci-ai-gateway/runtime/bootstrap.py"
        inode = path.stat().st_ino
        self.download.assert_called_once_with(manifest())
        self.download.reset_mock()
        prepare_sources(manifest(), self.root)
        self.download.assert_not_called()
        self.assertEqual(path.stat().st_ino, inode)

    def test_interrupted_download_leaves_no_files_and_can_retry(self):
        self.download.side_effect = ValueError("synthetic unavailable")
        with self.assertRaises(ValueError):
            prepare_sources(manifest(), self.root)
        self.assertFalse(list(self.root.iterdir()))
        self.download.side_effect = None
        prepare_sources(manifest(), self.root)
        self.assertTrue((self.root / "opt/oci-ai-gateway/runtime/bootstrap.py").exists())

    def test_missing_member_resumes_but_changed_member_is_preserved(self):
        prepare_sources(manifest(), self.root)
        path = self.root / "opt/oci-ai-gateway/runtime/bootstrap.py"
        path.unlink()
        prepare_sources(manifest(), self.root)
        self.assertEqual(path.read_text(), FILES["runtime/bootstrap.py"])
        path.write_text("changed")
        self.download.reset_mock()
        with self.assertRaises(ValueError):
            prepare_sources(manifest(), self.root)
        self.download.assert_not_called()
        self.assertEqual(path.read_text(), "changed")

    def test_main_reloads_downloaded_units_before_runtime_initialization(self):
        path = self.root / "source.json"
        path.write_text(json.dumps(manifest()))
        path.chmod(0o600)
        events = []
        import os
        actual_open = os.open
        with patch("runtime.source_bootstrap.os.geteuid", return_value=0), \
                patch("runtime.source_bootstrap.os.open", side_effect=lambda *a: actual_open(path, os.O_RDONLY)), \
                patch("runtime.source_bootstrap.os.fstat", return_value=type("Stat", (), {"st_mode": 0o100600, "st_uid": 0})()), \
                patch("runtime.source_bootstrap.prepare_sources", side_effect=lambda *a: events.append("sources")), \
                patch("runtime.host_commands._run", side_effect=lambda *a: events.append("reload")), \
                patch("runtime.bootstrap.main", side_effect=lambda: events.append("bootstrap") or 0):
            self.assertEqual(main(), 0)
        self.assertEqual(events, ["sources", "reload", "bootstrap"])

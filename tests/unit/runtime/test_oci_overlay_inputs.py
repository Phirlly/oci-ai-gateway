"""Source and patch drift fail before any application or returned code."""

import copy
from unittest.mock import patch

from runtime import oci_adapter_overlay as overlay
from tests.unit.runtime.overlay_fixture import OverlayCase


class OverlayInputs(OverlayCase):
    def test_exact_sources_produce_only_expected_results_repeatedly(self):
        original = copy.deepcopy(self.record)
        for _ in range(2):
            self.assertEqual(overlay.prepare_overlay(self.record), self.results)
            self.assertEqual(self.record, original)
            self.assert_clean()

    def test_invalid_shapes_paths_and_source_content_never_invoke_git(self):
        first = next(iter(self.sources))
        candidates = [None, [], {}, {**self.record, "extra": True},
                      {**self.record, "root": "/untrusted"},
                      {**self.record, "files": []}]
        for body in ("changed", None, "\ud800", "a" * 65537):
            candidates.append({**self.record, "files": {**self.sources, first: body}})
        candidates.append({**self.record, "files": {**self.sources, "../../outside": "bad"}})
        with patch.object(overlay.subprocess, "run") as run:
            for record in candidates:
                with self.subTest(record_type=type(record).__name__), self.assertRaisesRegex(
                        overlay.OverlayError, "^Native OCI adapter preparation failed$"):
                    overlay.prepare_overlay(record)
            run.assert_not_called()
        self.assert_clean()

    def test_patch_drift_and_oversize_fail_before_application(self):
        for content in (b"changed private marker", b"x" * 32769):
            self.change.write_bytes(content)
            with patch.object(overlay.subprocess, "run") as run:
                with self.assertRaises(overlay.OverlayError):
                    overlay.prepare_overlay(self.record)
                run.assert_not_called()
            self.assert_clean()

    def test_unexpected_result_hash_is_rejected(self):
        with patch.object(overlay, "RESULT_HASHES", overlay.SOURCE_HASHES):
            with self.assertRaises(overlay.OverlayError):
                overlay.prepare_overlay(self.record)
        self.assert_clean()

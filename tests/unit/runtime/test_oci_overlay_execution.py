"""Application failures are bounded, sanitized and clean their workspace."""

import hashlib
import os
import subprocess
from unittest.mock import patch

from runtime import oci_adapter_overlay as overlay
from tests.unit.runtime.overlay_fixture import OverlayCase, hashes


class OverlayExecution(OverlayCase):
    def test_failed_and_timed_out_git_leave_no_partial_output(self):
        for error in (OSError("private marker"), subprocess.TimeoutExpired("private marker", 15),
                      subprocess.CalledProcessError(1, "git", stderr="private marker")):
            with self.subTest(error=type(error).__name__):
                with patch.object(overlay.subprocess, "run", side_effect=error):
                    with self.assertRaisesRegex(overlay.OverlayError, "^Native OCI adapter preparation failed$"):
                        overlay.prepare_overlay(self.record)
                self.assert_clean()

    def test_check_precedes_apply_and_inherited_git_settings_are_removed(self):
        actual = subprocess.run
        with patch.dict(os.environ, {"GIT_DIR": "/private-marker", "GIT_CONFIG_COUNT": "99"}):
            with patch.object(overlay.subprocess, "run", wraps=actual) as run:
                self.assertEqual(overlay.prepare_overlay(self.record), self.results)
        self.assertEqual(run.call_count, 2)
        self.assertIn("--check", run.call_args_list[0].args[0])
        self.assertNotIn("--check", run.call_args_list[1].args[0])
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 15)
            self.assertEqual(call.kwargs["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
            self.assertNotIn("GIT_DIR", call.kwargs["env"])
            self.assertNotIn("GIT_CONFIG_COUNT", call.kwargs["env"])
        self.assert_clean()

    def test_matching_hash_does_not_allow_invalid_python(self):
        body = self.change.read_text().replace("+value = 2", "+def invalid(")
        self.change.write_text(body)
        bad_results = {name: "def invalid(\n" for name in self.results}
        with patch.object(overlay, "PATCH_HASH", hashlib.sha256(body.encode()).hexdigest()):
            with patch.object(overlay, "RESULT_HASHES", hashes(bad_results)):
                with self.assertRaises(overlay.OverlayError):
                    overlay.prepare_overlay(self.record)
        self.assert_clean()

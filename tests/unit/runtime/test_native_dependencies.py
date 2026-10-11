"""Native prerequisites must succeed before any container or socket activation."""

import subprocess
import unittest
from unittest.mock import patch

from runtime.gateway_http import GatewayError
from runtime.native_startup import ensure_native_dependencies, start_native_services


class NativeDependencyTests(unittest.TestCase):
    def setUp(self):
        self.phases = []
        self.failure = None
        self.sdk = "2.187.0"
        self.missing_git = False

        def run(command, phase, timeout, **kwargs):
            self.phases.append(phase)
            if phase == self.failure or (phase == "Git inspection" and self.missing_git):
                raise GatewayError("Synthetic prerequisite failure")
            return subprocess.CompletedProcess(command, 0, self.sdk, "")

        self.enterContext(patch("runtime.native_startup._run", side_effect=run))

    def test_verified_sdk_and_existing_git_need_no_installation(self):
        ensure_native_dependencies()
        self.assertEqual(self.phases, ["OCI SDK verification", "Git inspection"])

    def test_sdk_mismatch_stops_before_git_or_activation(self):
        self.sdk = "0.0.0"
        with self.assertRaisesRegex(GatewayError, "SDK version"):
            start_native_services(None)
        self.assertEqual(self.phases, ["OCI SDK verification"])

    def test_missing_git_is_installed_then_verified(self):
        self.missing_git = True
        ensure_native_dependencies()
        self.assertEqual(self.phases, ["OCI SDK verification", "Git inspection",
                                      "Git package index refresh", "Git package installation", "Git verification"])

    def test_failed_prerequisite_never_starts_containers_or_socket(self):
        for failure in ("OCI SDK verification", "Git package index refresh",
                        "Git package installation", "Git verification"):
            self.phases.clear()
            self.missing_git, self.failure = True, failure
            with self.subTest(failure=failure), self.assertRaises(GatewayError):
                start_native_services(None)
            self.assertEqual(self.phases[-1], failure)
            self.assertNotIn("Pinned container download", self.phases)

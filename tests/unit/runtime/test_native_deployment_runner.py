"""Synthetic Compose checks expose readable test output and preserve failures."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.contracts.native_deployment.stack import NativeStack


class NativeDeploymentRunnerTests(unittest.TestCase):
    def test_linux_requires_production_file_ownership_before_creating_inputs(self):
        owner = NativeStack()
        with patch("sys.platform", "linux"), patch("os.geteuid", return_value=1001), \
                patch("tests.contracts.runtime.stack.GatewayStack.prepare_inputs",
                      side_effect=AssertionError("Created inputs before prerequisite validation")) as create:
            with self.assertRaisesRegex(RuntimeError, "requires root"):
                owner.prepare_inputs()
        create.assert_not_called()

    def test_failed_container_assertions_remain_a_failed_contract(self):
        owner = NativeStack()
        with patch.object(owner, "command", return_value=["synthetic-compose"]), \
                patch.dict("os.environ", {"GATEWAY_TEST_MASTER_KEY": "synthetic"}), \
                patch("tests.contracts.native_deployment.stack.subprocess.run",
                      return_value=SimpleNamespace(returncode=1)) as run:
            with self.assertRaisesRegex(RuntimeError, "Native startup assertions failed"):
                owner.check_startup()
        self.assertNotIn("capture_output", run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs["timeout"], 45)

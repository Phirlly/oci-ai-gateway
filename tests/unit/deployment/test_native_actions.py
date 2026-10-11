"""Native workflow dispatch needs neither model-key TTL nor a model-key client."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from deployment.action_entrypoint import create_actions
from deployment.gateway_actions import GatewayActions
from deployment.gateway_config import GatewayConfig
from deployment.resource_manager_stacks import StackTarget
from .gateway_config_fixture import CONTEXT
from .native_fixture import NATIVE_SETTINGS


class NativeActionTests(unittest.TestCase):
    def test_deploy_passes_no_fabricated_expiry_and_keeps_readiness_gate(self):
        journal = Mock()
        journal.read.return_value = []
        target = StackTarget(GatewayConfig(NATIVE_SETTINGS), "a" * 64)
        actions = GatewayActions(Mock(), journal, target, Mock(), Mock(), vault=Mock())
        progress = SimpleNamespace(phase="CREDENTIALS_PUBLISHED", runtime_context=CONTEXT)
        with patch("deployment.gateway_actions.advance_handoff", return_value=progress) as advance, \
                patch.object(actions, "_wait_frontend"), \
                patch("deployment.gateway_actions.verify_demo", return_value={"ready": True, "samples": []}):
            self.assertTrue(actions.deploy("synthetic", "Synthetic9!Password")["ready"])
        self.assertIsNone(advance.call_args.kwargs["expires_at"])
        self.assertIsNone(advance.call_args.kwargs["keys"])

    def test_native_factory_does_not_construct_model_key_adapter(self):
        environment = {"GITHUB_REPOSITORY_ID": "17", "GITHUB_REPOSITORY": "synthetic/gateway",
                       "GITHUB_SHA": "a" * 40, "GITHUB_TOKEN": "synthetic"}
        connection = SimpleNamespace(profile="DEFAULT", config_file="synthetic")
        with patch("deployment.action_entrypoint.deployment_package", return_value=Mock(is_gateway=True, schema_version=3)), \
                patch("deployment.action_entrypoint.ModelKeysCLI") as keys, \
                patch("deployment.action_entrypoint.GitHubJournal") as journal, \
                patch("deployment.action_entrypoint.ResourceManagerCLI"), \
                patch("deployment.action_entrypoint.VaultCLI"), \
                patch("deployment.action_entrypoint.ComputeCLI"):
            journal.return_value.controller_id = "a" * 64
            for action in ("Deploy", "Remove"):
                create_actions(GatewayConfig(NATIVE_SETTINGS), connection, environment, action)
        keys.assert_not_called()

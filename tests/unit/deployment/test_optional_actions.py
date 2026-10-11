"""Fresh cloud writes require only selected provider keys; external-only has no OCI scope."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from deployment.credential_errors import DeliveryError
from deployment.gateway_actions import GatewayActions
from deployment.gateway_config import GatewayConfig
from deployment.resource_manager_stacks import StackTarget
from tests.unit.runtime.optional_fixture import SUBSETS
from .optional_fixture import settings


class OptionalActionTests(unittest.TestCase):
    def actions(self, providers):
        journal = Mock()
        journal.read.return_value = []
        return GatewayActions(Mock(), journal, StackTarget(GatewayConfig(settings(providers)), "a" * 64),
                              Mock(), Mock(), vault=Mock())

    def test_preflight_ignores_disabled_keys_and_passes_only_selected_keys(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers):
                actions = self.actions(providers)
                keys = {p + "_api_key": "synthetic" for p in providers if p != "oci"}
                progress = SimpleNamespace(phase="CREDENTIALS_PUBLISHED", runtime_context={"public_ip": "8.8.4.4"})
                with patch("deployment.gateway_actions.advance_handoff", return_value=progress) as advance, \
                        patch.object(actions, "_wait_frontend"), patch.object(actions, "_verify", return_value={"ready": True}):
                    actions.deploy(keys | {"disabled_key": "must-not-publish"}, "Synthetic9!Password")
                self.assertEqual(advance.call_args.kwargs["external_api_key"], keys)
                self.assertEqual(advance.call_args.kwargs["inference_region"], "us-ashburn-1" if "oci" in providers else None)
                self.assertEqual(len(actions.presenter.models), len(providers))

    def test_missing_selected_key_blocks_before_any_cloud_handoff(self):
        actions = self.actions(("openai",))
        with patch("deployment.gateway_actions.advance_handoff") as advance, self.assertRaises(DeliveryError):
            actions.deploy({}, "Synthetic9!Password")
        advance.assert_not_called()

    def test_runtime_incompatible_key_is_rejected_before_cloud_writes(self):
        actions = self.actions(("openai",))
        with patch("deployment.gateway_actions.advance_handoff") as advance, self.assertRaises(DeliveryError):
            actions.deploy({"openai_api_key": "synthetic-\u00e9"}, "Synthetic9!Password")
        advance.assert_not_called()

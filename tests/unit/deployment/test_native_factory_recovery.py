"""Factory policy preserves legacy archives and rejects cross-version inputs."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from deployment.action_entrypoint import create_actions
from deployment.credential_errors import DeliveryError
from deployment.foundation_package import GatewayPackage
from deployment.gateway_config import GatewayConfig
from deployment.resource_manager_stacks import StackTarget
from deployment.stack_submission import ensure_stack
from .gateway_config_fixture import GATEWAY_SETTINGS
from .native_fixture import NATIVE_SETTINGS
from .submission_fixtures import submission_fixture


class NativeFactoryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f = submission_fixture()
        self.environment = {"GITHUB_REPOSITORY_ID": "17", "GITHUB_REPOSITORY": "synthetic/gateway",
                            "GITHUB_SHA": "a" * 40, "GITHUB_TOKEN": "synthetic"}
        self.connection = SimpleNamespace(profile="DEFAULT", config_file="synthetic")
        self.enterContext(patch("deployment.action_entrypoint.GitHubJournal", return_value=self.f.journal))
        self.enterContext(patch("deployment.action_entrypoint.ResourceManagerCLI", return_value=self.f.orm))
        self.enterContext(patch("deployment.action_entrypoint.ComputeCLI"))
        self.vault = self.enterContext(patch("deployment.action_entrypoint.VaultCLI"))
        self.keys = self.enterContext(patch("deployment.action_entrypoint.ModelKeysCLI"))
        self.builder = self.enterContext(patch("deployment.action_entrypoint.NativePackage.build"))

    def create(self, settings, action="Status"):
        return create_actions(GatewayConfig(settings), self.connection, self.environment, action)

    def test_existing_legacy_archive_never_rebuilds_from_native_checkout(self):
        package = GatewayPackage.build(Path(__file__).resolve().parents[3])
        target = StackTarget(GatewayConfig(GATEWAY_SETTINGS), self.f.journal.controller_id)
        self.f.orm.package = package
        self.f.orm.get_stack_package = Mock(return_value=package.content)
        ensure_stack(self.f.orm, self.f.journal, target, package)
        actions = self.create(GATEWAY_SETTINGS)
        self.assertEqual(actions.package.content, package.content)
        self.builder.assert_not_called()

    def test_fresh_legacy_settings_stop_without_build_or_cloud_mutation(self):
        with self.assertRaisesRegex(DeliveryError, "Fresh deployments require version3"):
            self.create(GATEWAY_SETTINGS, "Deploy")
        self.builder.assert_not_called()
        self.assertFalse(self.f.orm.stacks)
        self.vault.assert_not_called()

    def test_both_schema_mismatches_stop_before_mutating_adapters(self):
        for settings, version in ((GATEWAY_SETTINGS, 3), (NATIVE_SETTINGS, 2)):
            with self.subTest(version=version), patch("deployment.action_entrypoint.deployment_package",
                    return_value=Mock(is_gateway=True, schema_version=version)):
                with self.assertRaisesRegex(DeliveryError, "schema differ"):
                    self.create(settings, "Deploy")
        self.vault.assert_not_called()
        self.keys.assert_not_called()

    def test_native_remove_constructs_neither_vault_nor_key_adapter(self):
        with patch("deployment.action_entrypoint.deployment_package",
                   return_value=Mock(is_gateway=True, schema_version=3)):
            self.create(NATIVE_SETTINGS, "Remove")
        self.vault.assert_not_called()
        self.keys.assert_not_called()

    def test_fresh_source_failure_precedes_journal_and_infrastructure_writes(self):
        self.builder.return_value.verify_public_source.side_effect = DeliveryError("Unpublished source")
        with self.assertRaisesRegex(DeliveryError, "Unpublished source"):
            self.create(NATIVE_SETTINGS, "Deploy")
        self.builder.assert_called_once()
        self.builder.return_value.verify_public_source.assert_called_once_with()
        self.assertFalse(self.f.orm.stacks)
        self.assertFalse(self.f.api.rows)
        self.vault.assert_not_called()

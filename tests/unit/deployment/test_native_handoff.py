"""One attested Apply publishes native credentials; cross-format submissions fail."""

import json
import unittest
from pathlib import Path

from deployment.credential_errors import DeliveryError
from deployment.foundation_package import GatewayPackage
from deployment.gateway_observation import observe_gateway
from .gateway_config_fixture import CONTEXT
from .native_handoff_fixture import NativeHandoffFixture


class NativeHandoffTests(unittest.TestCase):
    def setUp(self):
        self.f = NativeHandoffFixture()

    def test_successful_apply_publishes_without_key_client_or_second_apply(self):
        self.f.base_succeeded()
        result = self.f.advance(external_api_key="synthetic", demo_password="Synthetic9!Password")
        self.assertEqual(result.phase, "CREDENTIALS_PUBLISHED")
        self.assertEqual(result.runtime_context, CONTEXT)
        self.assertEqual(len(self.f.orm.jobs), 1)
        value = json.loads(self.f.vault.rows[self.f.vault.current][1])
        self.assertEqual(value["schema_version"], 3)
        before = dict(self.f.vault.rows)
        self.assertEqual(self.f.advance(), result)
        self.assertEqual(self.f.vault.rows, before)
        self.assertEqual(len(self.f.orm.jobs), 1)

    def test_pending_or_failed_apply_does_not_stage_credentials(self):
        self.f.advance()
        for state in ("ACCEPTED", "FAILED"):
            self.f.orm.jobs[0]["lifecycle-state"] = state
            self.assertEqual(self.f.advance().phase, "FOUNDATION")
            self.assertFalse(self.f.vault.mutations)

    def test_wrong_package_version_is_rejected_before_cloud_writes(self):
        self.f.package = GatewayPackage.build(Path(__file__).resolve().parents[3])
        self.f.orm.package = self.f.package
        with self.assertRaises(DeliveryError):
            self.f.advance()
        self.assertFalse(self.f.orm.stacks)

    def test_runtime_context_change_cannot_reuse_committed_credentials(self):
        self.f.base_succeeded()
        self.f.advance(external_api_key="synthetic", demo_password="Synthetic9!Password")
        before = dict(self.f.vault.rows)
        self.f.compute.public["ip-address"] = self.f.compute.vnic["public-ip"] = "8.8.8.8"
        with self.assertRaises(DeliveryError):
            self.f.advance()
        self.assertEqual(self.f.vault.rows, before)

    def test_native_infrastructure_observation_does_not_require_a_key_binding(self):
        self.f.base_succeeded()
        f = self.f
        observed = observe_gateway(f.orm, f.journal, f.target, f.package, f.compute)
        self.assertEqual(observed.phase, "DEPLOYED")
        self.assertEqual(observed.context, CONTEXT)
        self.assertFalse(f.vault.mutations)

"""Real schema4 handoff composes attestation, context and credential recovery."""

import json
import unittest

from deployment.credential_errors import DeliveryError
from deployment.gateway_observation import observe_gateway
from tests.unit.runtime.optional_fixture import SUBSETS
from .gateway_config_fixture import CONTEXT
from .optional_handoff_fixture import OptionalHandoffFixture


class OptionalHandoffTests(unittest.TestCase):
    def test_each_selection_publishes_once_and_resumes_without_provider_inputs(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers):
                fixture = OptionalHandoffFixture(providers)
                fixture.base_succeeded()
                keys = {name + "_api_key": "synthetic-" + name for name in providers if name != "oci"}
                result = fixture.advance(external_api_key=keys, demo_password="Synthetic9!Password")
                self.assertEqual(result.phase, "CREDENTIALS_PUBLISHED")
                expected = {key: value for key, value in CONTEXT.items()
                            if key not in {"external_provider", "external_model_id"}}
                self.assertEqual(result.runtime_context, expected)
                saved = dict(fixture.vault.rows)
                self.assertEqual(fixture.advance(), result)
                self.assertEqual(fixture.vault.rows, saved)
                self.assertEqual(len(fixture.orm.jobs), 1)
                stored = json.loads(fixture.vault.rows[fixture.vault.current][1])
                self.assertEqual(stored["identity"]["models"], fixture.target.config.values["models"])
                self.assertEqual("inference_region" in stored["identity"], "oci" in providers)
                observed = observe_gateway(fixture.orm, fixture.journal, fixture.target,
                                           fixture.package, fixture.compute)
                self.assertEqual(observed.context, expected)

    def test_external_only_resume_rejects_changed_owned_public_address(self):
        fixture = OptionalHandoffFixture()
        fixture.base_succeeded()
        fixture.advance(external_api_key={"openai_api_key": "synthetic"}, demo_password="Synthetic9!Password")
        saved = dict(fixture.vault.rows)
        fixture.compute.public["ip-address"] = fixture.compute.vnic["public-ip"] = "8.8.8.8"
        with self.assertRaises(DeliveryError):
            fixture.advance()
        self.assertEqual(fixture.vault.rows, saved)

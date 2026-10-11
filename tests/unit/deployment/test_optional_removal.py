"""External-only removal depends on attested ORM history, never VM or secrets."""

import unittest

from deployment.credential_errors import DeliveryError
from deployment.removal_handoff import advance_removal
from .destroy_fixture import DestroyORM
from .optional_handoff_fixture import OptionalHandoffFixture


class OptionalRemovalTests(unittest.TestCase):
    def test_remove_and_repeat_without_compute_vault_keys_or_inference_region(self):
        fixture = OptionalHandoffFixture()
        fixture.base_succeeded()
        fixture.advance(external_api_key={"openai_api_key": "synthetic"}, demo_password="Synthetic9!Password")
        fixture.compute = fixture.vault = fixture.keys = None
        fixture.orm.create_destroy = lambda payload: DestroyORM.create_destroy(fixture.orm, payload)

        def remove():
            return advance_removal(fixture.orm, fixture.journal, fixture.target, fixture.package,
                                   vault=None, keys=None, inference_region=None)

        self.assertEqual(remove().phase, "DESTROY")
        with self.assertRaises(DeliveryError):
            fixture.advance()
        fixture.orm.jobs[-1]["lifecycle-state"] = "SUCCEEDED"
        self.assertEqual(remove().job.state, "SUCCEEDED")
        self.assertEqual(remove().job.state, "SUCCEEDED")
        self.assertEqual(len(fixture.orm.jobs), 2)

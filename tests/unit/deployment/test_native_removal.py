"""Native Destroy uses attested controller history without VM or key services."""

import unittest

from deployment.credential_errors import DeliveryError
from deployment.removal_handoff import advance_removal
from deployment.submission_records import target_identity
from .destroy_fixture import DestroyORM
from .native_handoff_fixture import NativeHandoffFixture


class NativeRemovalTests(unittest.TestCase):
    def setUp(self):
        self.f = NativeHandoffFixture()
        self.f.orm.create_destroy = lambda payload: DestroyORM.create_destroy(self.f.orm, payload)

    def remove(self):
        f = self.f
        return advance_removal(f.orm, f.journal, f.target, f.package, vault=None, keys=None,
                               inference_region=f.target.config.values["inference_region"])

    def test_successful_base_removes_without_vault_keys_or_running_vm(self):
        self.f.base_succeeded()
        self.f.compute = None
        result = self.remove()
        self.assertEqual(result.phase, "DESTROY")
        kinds = [row.kind for row in self.f.journal.read(target_identity(self.f.target.config))]
        self.assertLess(kinds.index("cleanup-start"), kinds.index("cleanup-complete"))
        self.assertLess(kinds.index("cleanup-complete"), kinds.index("destroy"))
        with self.assertRaises(DeliveryError):
            self.f.advance()
        self.f.orm.jobs[-1]["lifecycle-state"] = "SUCCEEDED"
        self.assertEqual(self.remove().job.state, "SUCCEEDED")
        self.assertEqual(len(self.f.orm.jobs), 2)

    def test_active_apply_is_observed_without_starting_cleanup(self):
        self.f.advance()
        self.assertEqual(self.remove().phase, "WAIT_FOR_INFRASTRUCTURE")
        kinds = [row.kind for row in self.f.journal.read(target_identity(self.f.target.config))]
        self.assertNotIn("cleanup-start", kinds)

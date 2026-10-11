"""Native credentials resume exact Vault versions without OCI key creation."""

import json
import unittest

from deployment.credential_errors import DeliveryError, VaultReadError
from deployment.credential_records import parse_record
from deployment.native_credentials import prepare_native_credentials
from .gateway_config_fixture import CONTEXT
from .native_fixture import native_document
from .record_fixtures import IDENTITY
from .vault_fixture import MemoryVault, delivery, record


class NativeCredentialDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.vault = MemoryVault()
        self.delivery = delivery(self.vault)

    def prepare(self, **inputs):
        return prepare_native_credentials(self.delivery, runtime_context=CONTEXT, **inputs)

    def test_first_bundle_stages_without_intent_then_publishes_exact_version(self):
        receipt = self.prepare(external_api_key="synthetic-external", demo_password="Synthetic9!Password")
        self.assertEqual(receipt.phase, "PENDING")
        self.assertIsNone(receipt.model_key_ocid)
        self.assertEqual(len(self.vault.rows), 2)
        value = json.loads(self.vault.rows[receipt.version_number][1])
        self.assertEqual(value["schema_version"], 3)
        self.assertNotIn("oci_api_key", value["credentials"])
        self.assertEqual(value["runtime"], CONTEXT)
        published = self.delivery.publish(receipt.version_name, None)
        saved = dict(self.vault.rows)
        self.assertEqual(self.prepare(demo_password="Changed9!Password"), published)
        self.assertEqual(self.vault.rows, saved)

    def test_saved_pending_is_reused_without_new_supplied_secrets(self):
        self.vault.add(parse_record(json.dumps(native_document()).encode(), IDENTITY))
        before = dict(self.vault.rows)
        self.assertEqual(self.prepare().phase, "PENDING")
        self.assertEqual(self.vault.rows, before)
        self.assertFalse(self.vault.mutations)

    def test_lost_staging_and_promotion_replies_use_exact_readback(self):
        self.vault.lose_stage_reply = self.vault.lose_promote_reply = True
        staged = self.prepare(external_api_key="synthetic-external", demo_password="Synthetic9!Password")
        self.delivery.publish(staged.version_name, None)
        self.assertEqual(self.prepare().phase, "CURRENT")
        self.assertEqual([row[0] for row in self.vault.mutations], ["stage", "promote"])

    def test_legacy_or_changed_context_stops_before_mutation(self):
        for saved in (record("creation-intent"), record(),
                      parse_record(json.dumps(native_document() | {"runtime": CONTEXT | {"public_ip": "8.8.8.8"}}).encode(), IDENTITY)):
            with self.subTest(kind=saved.kind):
                self.vault = MemoryVault()
                self.vault.add(saved, current=saved.kind == "runtime-bundle")
                self.delivery = delivery(self.vault)
                with self.assertRaises(DeliveryError):
                    self.prepare()
                self.assertFalse(self.vault.mutations)

    def test_unconfirmed_upload_is_not_replayed_in_the_same_invocation(self):
        self.vault.reject_stage = True
        with self.assertRaises(VaultReadError):
            self.prepare(external_api_key="synthetic-external", demo_password="Synthetic9!Password")
        self.assertEqual(len(self.vault.mutations), 1)
        self.assertEqual(self.vault.current, 1)

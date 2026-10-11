"""Selected keys are staged once, recovered exactly and never reset on resume."""

import json
import unittest

from deployment.native_credentials import prepare_native_credentials
from deployment.secret_delivery import SecretDelivery
from deployment.vault_state import VaultTarget
from tests.unit.runtime.optional_fixture import SUBSETS, document
from .record_fixtures import NOW
from .vault_fixture import ENCRYPTION_KEY_ID, MemoryVault, VAULT_ID


class OptionalCredentialDeliveryTests(unittest.TestCase):
    def test_selected_key_map_publishes_then_resumes_without_supplied_keys(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers):
                value = document(providers)
                vault = MemoryVault(value["identity"])
                target = VaultTarget(value["identity"], VAULT_ID, ENCRYPTION_KEY_ID)
                delivery = SecretDelivery(vault, target, now=lambda: NOW)
                keys = {name + "_api_key": "synthetic-" + name for name in providers if name != "oci"}
                receipt = prepare_native_credentials(delivery, runtime_context=value["runtime"],
                    external_api_key=keys, demo_password="Synthetic9!Passwörd")
                published = delivery.publish(receipt.version_name, None)
                saved = dict(vault.rows)
                self.assertEqual(prepare_native_credentials(delivery, runtime_context=value["runtime"]), published)
                self.assertEqual(vault.rows, saved)
                stored = json.loads(vault.rows[vault.current][1])
                self.assertEqual(stored["schema_version"], 4)
                self.assertEqual(stored["credentials"]["demo_password"], "Synthetic9!Passwörd")
                self.assertEqual(set(stored["credentials"]) & {"anthropic_api_key", "openai_api_key"}, set(keys))

    def test_target_copies_nested_selection(self):
        identity = document(("openai",))["identity"]
        target = VaultTarget(identity, VAULT_ID, ENCRYPTION_KEY_ID)
        original = target.identity["models"]["openai"]
        identity["models"]["openai"] = "changed"
        target.identity["models"]["openai"] = "changed-again"
        self.assertEqual(target.identity["models"]["openai"], original)

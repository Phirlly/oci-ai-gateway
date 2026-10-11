"""Schema4 bundles bind enabled routes, required keys and exact VM ownership."""

import json
import unittest

from runtime.gateway_http import GatewayError
from runtime.runtime_bundle import load_bundle
from .optional_fixture import INSTANCE, SUBSETS, credentials, document, settings


class OptionalBundleTests(unittest.TestCase):
    def test_each_selection_loads_only_its_credentials_and_presenter_models(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers):
                value = document(providers)
                loaded = load_bundle(json.dumps(value).encode(), settings(providers), INSTANCE)
                self.assertEqual(dict(loaded.credentials), credentials(providers))
                self.assertEqual(len(loaded.presenter.models), len(providers))

    def test_missing_or_disabled_provider_keys_fail_closed(self):
        for fields in ({}, {"openai_api_key": "secret", "anthropic_api_key": "disabled"}):
            value = document(("openai",))
            del value["credentials"]["openai_api_key"]
            value["credentials"].update(fields)
            with self.assertRaises(GatewayError):
                load_bundle(json.dumps(value).encode(), settings(("openai",)), INSTANCE)

    def test_preserves_existing_unicode_presenter_password_policy(self):
        value = document(("openai",))
        value["credentials"]["demo_password"] = "Synthetic9!Passwörd"
        loaded = load_bundle(json.dumps(value).encode(), settings(("openai",)), INSTANCE)
        self.assertEqual(loaded.credentials["demo_password"], "Synthetic9!Passwörd")

    def test_changed_selection_or_instance_cannot_use_saved_bundle(self):
        value = document(("openai",))
        for config, instance in ((settings(("anthropic",)), INSTANCE),
                                 (settings(("openai",)), "ocid1.instance.oc1.iad.other")):
            with self.assertRaises(GatewayError):
                load_bundle(json.dumps(value).encode(), config, instance)

    def test_optional_identity_cannot_be_reinterpreted_as_legacy_schema(self):
        value = document(("openai",))
        value["schema_version"] = 3
        with self.assertRaises(GatewayError):
            load_bundle(json.dumps(value).encode(), settings(("openai",)), INSTANCE)

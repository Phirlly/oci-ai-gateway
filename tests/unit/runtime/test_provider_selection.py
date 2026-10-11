"""Only explicitly selected providers define routes and credential requirements."""

import unittest

from runtime.gateway_http import GatewayError
from runtime.runtime_bundle import validate_settings
from runtime.provider_selection import model_aliases, provider_keys, validate_models
from .optional_fixture import MODELS, SUBSETS, settings


class ProviderSelectionTests(unittest.TestCase):
    def test_all_seven_selections_have_exact_aliases_and_keys(self):
        aliases = {"oci": "oci-managed", "anthropic": "external-anthropic", "openai": "external-openai"}
        for providers in SUBSETS:
            with self.subTest(providers=providers):
                value = settings(providers)
                self.assertEqual(validate_settings(value), value)
                self.assertEqual(model_aliases(value), tuple(aliases[p] for p in MODELS if p in providers))
                self.assertEqual(provider_keys(value), {p + "_api_key" for p in providers if p != "oci"})

    def test_selection_rejects_empty_unknown_provider_and_invalid_model(self):
        for models in ({}, {"other": "a"}, {"openai": ""}, {"openai": "x/y"},
                       {"oci": None}, [], {"openai": "a" * 256}):
            with self.subTest(models=models), self.assertRaises(GatewayError):
                validate_models(models)

    def test_inference_region_is_required_only_with_oci_and_forbidden_without_it(self):
        native = settings(("oci",))
        del native["inference_region"]
        for value in (native, settings(("openai",)) | {"inference_region": "us-ashburn-1"},
                      settings() | {"external_provider": "anthropic"}):
            with self.assertRaises(GatewayError):
                validate_settings(value)

"""Console secret authority matches the enabled external providers exactly."""

import unittest

from runtime.console_settings import validate_console_settings
from runtime.gateway_http import GatewayError
from .optional_console_fixture import settings
from .optional_fixture import SUBSETS


class OptionalConsoleSettingsTests(unittest.TestCase):
    def test_each_selection_has_exact_distinct_external_secret_ids(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers):
                value = settings(providers)
                self.assertEqual(validate_console_settings(value), value)

    def test_missing_extra_or_overlapping_secret_ids_are_rejected(self):
        value = settings(("openai",))
        for secrets in ({}, {"openai": value["presenter_secret_ocid"]},
                        {"openai": value["runtime"]["secret_ocid"]},
                        {"openai": "invalid"}, value["provider_secrets"] | {"anthropic": "ocid1.vaultsecret.oc1.iad.extra"}):
            with self.subTest(secrets=secrets), self.assertRaises(GatewayError):
                validate_console_settings(value | {"provider_secrets": secrets})

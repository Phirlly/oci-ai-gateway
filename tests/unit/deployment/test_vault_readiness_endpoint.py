"""The stack probe can contact only its OC1 Vault management endpoint."""

import unittest

from orm.vault_readiness import validated_host


class VaultEndpointTests(unittest.TestCase):
    def test_provider_endpoint_accepts_only_optional_root_slash(self):
        for region in ("us-ashburn-1", "eu-frankfurt-1"):
            host = "example-management.kms." + region + ".oraclecloud.com"
            for suffix in ("", "/"):
                self.assertEqual(validated_host("https://" + host + suffix, region), host)

    def test_rejects_endpoint_or_region_redirection(self):
        host = "example-management.kms.us-ashburn-1.oraclecloud.com"
        for endpoint in (
            "http://" + host, "https://user@" + host, "https://" + host + ":443",
            "https://" + host + "/keys", "https://" + host + "?x=1",
            "https://" + host + "#x", "https://" + host + ".evil.invalid",
            "https://" + host + "\n", " https://" + host, "https://127.0.0.1",
            "https://example-crypto.kms.us-ashburn-1.oraclecloud.com",
            "https://example-management.kms.eu-frankfurt-1.oraclecloud.com", "",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                validated_host(endpoint, "us-ashburn-1")
        for region in ("", ".*", "us-ashburn-1\n"):
            with self.assertRaises(ValueError):
                validated_host("https://" + host, region)

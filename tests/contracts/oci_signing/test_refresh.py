"""Real SDK token expiry and key rotation must remain atomic and fail closed."""

import unittest
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature

from runtime.oci_instance_signer import SigningUnavailable
from tests.unit.runtime.oci_signing_fixture import chat_body
from .federation_fixture import FederationFixture, verify_signature


class RefreshContracts(unittest.TestCase):
    def setUp(self):
        self.fixture = FederationFixture(self)

    def test_unexpired_token_is_reused_without_an_authentication_request(self):
        body = chat_body()
        first = self.fixture.signer.sign(body)
        second = self.fixture.signer.sign(body)
        self.assertEqual(self.fixture.issue.call_count, 1)
        public = self.fixture.issued[0][1]
        verify_signature(first, public, body=body)
        verify_signature(second, public, body=body)

    def test_expiring_token_uses_new_token_and_matching_new_key(self):
        body = chat_body()
        first = self.fixture.signer.sign(body)
        self.fixture.clock.return_value = 4550  # Inside SDK's sixty-second jitter.
        second = self.fixture.signer.sign(body)
        self.assertEqual(self.fixture.issue.call_count, 2)
        old_token, old_public = self.fixture.issued[0]
        new_token, new_public = self.fixture.issued[1]
        self.assertNotEqual(old_token, new_token)
        self.assertIn('keyId="ST$' + new_token + '"', second["authorization"])
        verify_signature(first, old_public, body=body)
        verify_signature(second, new_public, body=body)
        with self.assertRaises(InvalidSignature):
            verify_signature(second, old_public, body=body)

    def test_failed_refresh_after_key_rotation_never_signs_or_retries(self):
        self.fixture.signer.sign(chat_body())
        previous_key = self.fixture.supplier.get_key_pair()["private"]
        self.fixture.clock.return_value = 4550
        self.fixture.issue.side_effect = RuntimeError("PRIVATE-KEY-SENTINEL")
        with patch.object(self.fixture.delegate, "do_request_sign", wraps=self.fixture.delegate.do_request_sign) as sign:
            for attempt in range(2):
                with self.subTest(attempt=attempt), self.assertRaises(SigningUnavailable) as raised:
                    self.fixture.signer.sign(chat_body())
                self.assertNotIn("SENTINEL", str(raised.exception))
            sign.assert_not_called()
        self.assertIsNot(self.fixture.supplier.get_key_pair()["private"], previous_key)
        self.assertEqual(self.fixture.issue.call_count, 2)

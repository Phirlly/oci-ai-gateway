"""Real SDK signatures bind exact body bytes, endpoint and configured model."""

import base64
import hashlib
import unittest

import oci
from cryptography.exceptions import InvalidSignature

from runtime.oci_signing_scope import SigningRejected
from tests.unit.runtime.oci_signing_fixture import chat_body
from .federation_fixture import FederationFixture, verify_signature


class SignatureContracts(unittest.TestCase):
    def setUp(self):
        self.assertEqual(oci.__version__, "2.187.0")
        self.fixture = FederationFixture(self)

    def test_exact_bytes_are_signed_with_content_headers(self):
        body = chat_body().replace(b': ', b':  ')
        headers = self.fixture.signer.sign(body)
        token, public = self.fixture.issued[-1]
        self.assertIn('keyId="ST$' + token + '"', headers["authorization"])
        self.assertEqual(headers["x-content-sha256"], base64.b64encode(hashlib.sha256(body).digest()).decode())
        self.assertEqual(headers["content-length"], str(len(body)))
        verify_signature(headers, public, body=body)

    def test_signature_cannot_authorize_changed_body_or_path(self):
        body = chat_body()
        headers = self.fixture.signer.sign(body)
        public = self.fixture.issued[-1][1]
        with self.assertRaises(InvalidSignature):
            verify_signature(headers, public, body=body.replace(b'Classify', b'Altered'))
        with self.assertRaises(InvalidSignature):
            verify_signature(headers, public, body=body, path="/20231130/actions/embedText")

    def test_injected_hash_field_cannot_authorize_another_body(self):
        with self.assertRaises(SigningRejected):
            self.fixture.signer.sign(chat_body(**{"x-content-sha256": "attacker hash"}))
        with self.assertRaises(TypeError):
            self.fixture.signer.sign(chat_body(), headers={"x-content-sha256": "attacker hash"})
        self.assertEqual(self.fixture.issue.call_count, 1)  # Fixture's initial synthetic token only.

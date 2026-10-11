"""Only bounded, unambiguous requests for the configured native model may be signed."""

import unittest

from runtime.oci_signing_scope import SigningScope, SigningRejected
from .oci_signing_fixture import COMPARTMENT, MODEL, REGION, chat_body


class SigningScopeTests(unittest.TestCase):
    def setUp(self):
        self.scope = SigningScope(REGION, COMPARTMENT, MODEL)

    def test_exact_bytes_survive_validation_and_endpoint_is_fixed(self):
        raw = chat_body().replace(b': ', b':  ')
        self.assertIs(self.scope.validate(raw), raw)
        self.assertEqual(self.scope.url,
                         "https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com/20231130/actions/chat")

    def test_wrong_compartment_model_or_serving_mode_is_denied(self):
        cases = [chat_body(compartmentId="ocid1.compartment.oc1..other"),
                 chat_body(servingMode={"servingType": "ON_DEMAND", "modelId": "other"}),
                 chat_body(servingMode={"servingType": "DEDICATED", "endpointId": "other"}),
                 chat_body(servingMode={"servingType": "ON_DEMAND", "modelId": MODEL, "extra": 1}),
                 chat_body(extra="private sentinel")]
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(SigningRejected) as raised:
                self.scope.validate(raw)
            self.assertNotIn("sentinel", str(raised.exception))

    def test_invalid_utf8_duplicate_keys_nonfinite_and_deep_json_are_denied(self):
        raw = chat_body()
        cases = [raw.decode(), b"[]", b"null", b"{}", b"not-json", b"\xff",
                 raw.decode().encode("utf-16"),
                 raw.replace(b'"maxTokens": 256', b'"maxTokens": 256, "maxTokens": 1'),
                 raw.replace(b'"maxTokens": 256', b'"maxTokens": 256, "temperature": NaN'),
                 raw.replace(b'"maxTokens": 256', b'"maxTokens": 256, "temperature": 1e309'),
                 raw.replace(b'"maxTokens": 256', b'"maxTokens": 256, "extra": ' + b'[' * 40 + b'0' + b']' * 40),
                 raw.replace(b'Classify a synthetic request.', b'\\ud800'),
                 raw + b" " * (256 * 1024)]
        for index, value in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(SigningRejected):
                self.scope.validate(value)

    def test_token_budget_is_explicit_integer_and_bounded(self):
        for limit in (None, True, 0, -1, 4097, 1.5, "256"):
            body = {"apiFormat": "GENERIC", "maxTokens": limit}
            with self.subTest(limit=limit), self.assertRaises(SigningRejected):
                self.scope.validate(chat_body(chatRequest=body))
        for limit in (1, 4096):
            self.scope.validate(chat_body(chatRequest={"apiFormat": "GENERIC", "maxTokens": limit}))
        for body in ({"apiFormat": "GENERIC"}, {"apiFormat": "COHERE", "maxTokens": 256}, None):
            with self.subTest(body=body), self.assertRaises(SigningRejected):
                self.scope.validate(chat_body(chatRequest=body))

    def test_invalid_scope_configuration_is_rejected(self):
        for values in (("us-ashburn-1/redirect", COMPARTMENT, MODEL),
                       (REGION, "another-compartment", MODEL), (REGION, COMPARTMENT, "oci/other")):
            with self.subTest(values=values), self.assertRaises(SigningRejected):
                SigningScope(*values)

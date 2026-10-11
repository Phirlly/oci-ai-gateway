"""Authorize the exact LiteLLM request before contacting the host signer."""

import base64
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from runtime.gateway_http import GatewayError
from runtime.oci_signing_client import SocketSigner
from runtime.oci_signing_scope import SigningRejected, SigningScope
from tests.unit.runtime.oci_signing_fixture import COMPARTMENT, MODEL, REGION, chat_body


class SigningClientTests(unittest.TestCase):
    def setUp(self):
        self.scope = SigningScope(REGION, COMPARTMENT, MODEL)
        self.client = SocketSigner(self.scope)
        self.body = chat_body()
        self.request = SimpleNamespace(method="POST", url=self.scope.url, body=self.body,
                                       headers={"content-type": "application/json",
                                                "content-length": str(len(self.body)),
                                                "user-agent": "litellm/synthetic"})
        self.headers = {"authorization": "Signature synthetic", "date": "Sat, 10 Oct 2026 12:00:00 GMT",
                        "host": self.scope.host, "content-type": "application/json",
                        "content-length": str(len(self.body)), "x-content-sha256":
                        base64.b64encode(hashlib.sha256(self.body).digest()).decode()}
        self.exchange = self.enterContext(patch("runtime.oci_signing_client.exchange"))
        self.exchange.return_value = json.dumps({"status": "ok", "headers": self.headers}).encode()

    def test_success_sends_only_exact_bytes_and_updates_same_request(self):
        result = self.client.do_request_sign(self.request, enforce_content_headers=True)
        self.assertIs(result, self.request)
        self.assertIs(self.exchange.call_args.args[1], self.body)
        self.assertEqual(self.request.headers, {"user-agent": "litellm/synthetic", **self.headers})

    def test_method_endpoint_body_and_scope_overrides_never_contact_host(self):
        for attribute, value in (("method", "GET"), ("url", self.scope.url + "?redirect=1"),
                                 ("body", self.body.decode()),
                                 ("body", chat_body(compartmentId="foreign"))):
            with self.subTest(attribute=attribute), patch.object(self.request, attribute, value):
                with self.assertRaises(SigningRejected):
                    self.client.do_request_sign(self.request)
        with self.assertRaises(SigningRejected):
            self.client.do_request_sign(self.request, enforce_content_headers=False)
        self.exchange.assert_not_called()

    def test_injected_headers_case_duplicates_and_false_length_are_rejected(self):
        for extra in ({"Host": "evil.invalid"}, {"authorization": "stolen"},
                      {"x-content-sha256": "stale"}, {"Content-Type": "application/json"},
                      {"content-length": "1"}, {"user-agent": "unsafe\r\nheader"}):
            with self.subTest(extra=extra), patch.object(self.request, "headers", self.request.headers | extra):
                with self.assertRaises(SigningRejected):
                    self.client.do_request_sign(self.request)
        self.exchange.assert_not_called()

    def test_wrong_response_scope_hash_or_extra_fields_never_mutate_request(self):
        original = dict(self.request.headers)
        for headers in (self.headers | {"host": "foreign.invalid"},
                        self.headers | {"x-content-sha256": "wrong"},
                        self.headers | {"content-length": "1"},
                        self.headers | {"extra": "value"},
                        self.headers | {"date": "unsafe\nvalue"}):
            with self.subTest(headers=headers):
                self.exchange.return_value = json.dumps({"status": "ok", "headers": headers}).encode()
                with self.assertRaisesRegex(GatewayError, "Native signing unavailable"):
                    self.client.do_request_sign(self.request)
                self.assertEqual(self.request.headers, original)

    def test_unknown_duplicate_or_private_response_is_sanitized(self):
        for reply in (b'{"status":"ok","status":"ok"}', b'private-credential-marker',
                      b'{"status":"unavailable","detail":"private-credential-marker"}',
                      b'{"status":"ok","headers":null}', b'[]'):
            with self.subTest(reply=reply):
                self.exchange.return_value = reply
                with self.assertRaisesRegex(GatewayError, "^Native signing unavailable$"):
                    self.client.do_request_sign(self.request)

    def test_host_rejection_has_fixed_error(self):
        self.exchange.return_value = b'{"status":"rejected"}'
        with self.assertRaisesRegex(SigningRejected, "^Native signing request rejected$"):
            self.client.do_request_sign(self.request)

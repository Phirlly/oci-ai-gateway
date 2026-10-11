"""Host signer ownership, fixed SDK construction and fail-closed lifetime."""

import os
import unittest
from threading import Thread
from unittest.mock import patch

from runtime.oci_instance_signer import InstanceSigner, SigningUnavailable
from runtime.oci_signing_scope import SigningScope, SigningRejected
from .oci_signing_fixture import CallableIdentity, COMPARTMENT, MODEL, REGION, TENANCY, chat_body, sdk


class InstanceSignerTests(unittest.TestCase):
    def setUp(self):
        self.identity = CallableIdentity()
        self.sdk = sdk(self.identity)
        self.loader = self.enterContext(patch("runtime.oci_instance_signer._load_sdk", return_value=self.sdk))
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.signer = InstanceSigner(SigningScope(REGION, COMPARTMENT, MODEL), TENANCY, REGION)

    def test_valid_request_uses_callable_with_fresh_headers_and_reuses_identity(self):
        body = chat_body()
        first = self.signer.sign(body)
        self.signer.sign(body)
        self.assertEqual(len(self.identity.calls), 2)
        request, enforce_body = self.identity.calls[0]
        self.assertTrue(enforce_body)
        self.assertIs(request.body, body)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path_url, "/20231130/actions/chat")
        self.assertEqual(set(first), {"authorization", "date", "host", "content-type", "content-length", "x-content-sha256"})
        self.assertEqual(first["content-length"], str(len(body)))
        self.assertIsNot(self.identity.calls[0][0].headers, self.identity.calls[1][0].headers)
        constructor = self.sdk.auth.signers.InstancePrincipalsSecurityTokenSigner
        constructor.assert_called_once()
        self.assertIs(constructor.call_args.kwargs["log_requests"], False)
        self.assertEqual(constructor.call_args.kwargs["retry_strategy"], self.sdk.retry.NoneRetryStrategy.return_value)
        self.assertEqual(constructor.call_args.kwargs["federation_client_retry_strategy"], self.sdk.retry.NoneRetryStrategy.return_value)
        self.assertEqual(os.environ["OCI_METADATA_BASE_URL"], "http://169.254.169.254/opc/v2")

    def test_rejected_body_never_loads_sdk_and_does_not_poison_identity(self):
        with self.assertRaises(SigningRejected):
            self.signer.sign(b"{}")
        self.loader.assert_not_called()
        self.signer.sign(chat_body())

    def test_wrong_sdk_version_stops_before_instance_construction(self):
        self.sdk.__version__ = "2.184.2"
        self.assert_unavailable()
        self.sdk.auth.signers.InstancePrincipalsSecurityTokenSigner.assert_not_called()

    def test_wrong_identity_stops_before_signing(self):
        for field, value in (("tenancy_id", "other"), ("region", "us-chicago-1")):
            with self.subTest(field=field):
                identity = CallableIdentity()
                setattr(identity, field, value)
                self.sdk.auth.signers.InstancePrincipalsSecurityTokenSigner.return_value = identity
                self.signer = InstanceSigner(SigningScope(REGION, COMPARTMENT, MODEL), TENANCY, REGION)
                self.assert_unavailable()
                self.assertEqual(identity.calls, [])

    def test_constructor_failure_is_sanitized_and_never_retried(self):
        constructor = self.sdk.auth.signers.InstancePrincipalsSecurityTokenSigner
        constructor.side_effect = RuntimeError("PRIVATE-KEY-SENTINEL")
        self.assert_unavailable()
        self.assert_unavailable()
        constructor.assert_called_once()

    def test_refresh_failure_invalidates_identity_without_reconstruction(self):
        self.signer.sign(chat_body())
        with patch.object(CallableIdentity, "__call__", side_effect=RuntimeError("PRIVATE-KEY-SENTINEL")) as call:
            self.assert_unavailable()
            self.assert_unavailable()
        call.assert_called_once()
        self.sdk.auth.signers.InstancePrincipalsSecurityTokenSigner.assert_called_once()

    def test_metadata_override_is_rejected_before_loading_sdk(self):
        os.environ["OCI_METADATA_BASE_URL"] = "http://private-sentinel.invalid"
        self.assert_unavailable()
        self.loader.assert_not_called()

    def test_secondary_thread_cannot_access_identity_or_invalidate_main_owner(self):
        errors = []
        def attempt():
            try:
                self.signer.sign(chat_body())
            except SigningUnavailable:
                errors.append(True)
        worker = Thread(target=attempt)
        worker.start()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [True])
        self.loader.assert_not_called()
        self.signer.sign(chat_body())

    def assert_unavailable(self):
        with self.assertRaises(SigningUnavailable) as raised:
            self.signer.sign(chat_body())
        self.assertNotIn("SENTINEL", str(raised.exception))
        self.assertNotIn("private-sentinel", str(raised.exception))

"""Construction and refresh share a finite main-thread deadline."""

import os
import signal
import time
import unittest
from unittest.mock import patch

from runtime.oci_instance_signer import InstanceSigner, SigningUnavailable
from runtime.oci_signing_scope import SigningScope
from .oci_signing_fixture import CallableIdentity, COMPARTMENT, MODEL, REGION, TENANCY, chat_body, sdk


class SigningDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.identity = CallableIdentity()
        self.sdk = sdk(self.identity)
        self.enterContext(patch("runtime.oci_instance_signer._load_sdk", return_value=self.sdk))
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.signer = InstanceSigner(SigningScope(REGION, COMPARTMENT, MODEL), TENANCY, REGION)
        self.handler = signal.getsignal(signal.SIGALRM)

    def tearDown(self):
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        self.assertEqual(signal.getsignal(signal.SIGALRM), self.handler)

    def assert_bounded_failure(self):
        start = time.monotonic()
        with self.assertRaises(SigningUnavailable):
            self.signer.sign(chat_body(), timeout=0.05)
        self.assertLess(time.monotonic() - start, 1)
        with self.assertRaises(SigningUnavailable):
            self.signer.sign(chat_body())

    def test_constructor_is_bounded(self):
        self.sdk.auth.signers.InstancePrincipalsSecurityTokenSigner.side_effect = lambda **kwargs: time.sleep(2)
        self.assert_bounded_failure()
        self.sdk.auth.signers.InstancePrincipalsSecurityTokenSigner.assert_called_once()

    def test_callable_refresh_is_bounded_and_not_replayed(self):
        self.signer.sign(chat_body())
        with patch.object(CallableIdentity, "__call__", side_effect=lambda *args, **kwargs: time.sleep(2)) as call:
            self.assert_bounded_failure()
        call.assert_called_once()

    def test_existing_timer_is_not_replaced(self):
        with patch("signal.getitimer", return_value=(10.0, 0.0)), patch("signal.setitimer") as timer:
            with self.assertRaises(SigningUnavailable):
                self.signer.sign(chat_body())
            timer.assert_not_called()
        self.sdk.auth.signers.InstancePrincipalsSecurityTokenSigner.assert_not_called()

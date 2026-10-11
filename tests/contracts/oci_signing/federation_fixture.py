"""Real SDK refresh/signing with in-memory keys and a synthetic token issuer."""

import base64
import hashlib
import re
from unittest.mock import Mock, patch

import jwt
import oci
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from oci.auth.federation_client import X509FederationClient
from oci.auth.security_token_container import SecurityTokenContainer
from oci.auth.session_key_supplier import SessionKeySupplier
from oci.auth.signers.security_token_signer import X509FederationClientBasedSecurityTokenSigner

from runtime.oci_instance_signer import InstanceSigner
from runtime.oci_signing_scope import SigningScope
from tests.unit.runtime.oci_signing_fixture import COMPARTMENT, MODEL, REGION, TENANCY


class FederationFixture:
    def __init__(self, test):
        test.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")))
        test.enterContext(patch("socket.create_connection", side_effect=AssertionError("Network forbidden")))
        test.enterContext(patch("oci.config.from_file", side_effect=AssertionError("Credentials forbidden")))
        self.clock = test.enterContext(patch("oci.auth.security_token_container.time.time", return_value=1000))
        test.enterContext(patch("oci.auth.auth_utils.get_tenancy_id_from_certificate", return_value=TENANCY))
        self.supplier = SessionKeySupplier()
        self.federation = X509FederationClient(
            federation_endpoint="https://synthetic.invalid/v1/x509", tenancy_id=TENANCY,
            session_key_supplier=self.supplier, leaf_certificate_retriever=Mock(),
            retry_strategy=oci.retry.NoneRetryStrategy(),
            circuit_breaker_strategy=oci.circuit_breaker.NoCircuitBreakerStrategy(), log_requests=False)
        test.addCleanup(self.federation.requests_session.close)
        self.issued = []
        self.issue = Mock(side_effect=self._issue)
        self.federation._get_security_token_from_auth_service = self.issue
        self.delegate = X509FederationClientBasedSecurityTokenSigner(self.federation)
        self.delegate.tenancy_id, self.delegate.region = TENANCY, REGION
        test.enterContext(patch("oci.auth.signers.InstancePrincipalsSecurityTokenSigner", return_value=self.delegate))
        self.signer = InstanceSigner(SigningScope(REGION, COMPARTMENT, MODEL), TENANCY, REGION)

    def _issue(self):
        token = jwt.encode({"iat": self.clock.return_value, "exp": self.clock.return_value + 3600,
                            "synthetic_sequence": len(self.issued)},
                           "synthetic-contract-key-not-a-real-secret-123456789", algorithm="HS256")
        self.federation.security_token = SecurityTokenContainer(self.supplier, token)
        self.issued.append((token, self.supplier.get_key_pair()["public"]))


def verify_signature(headers, public_key, *, body, path="/20231130/actions/chat"):
    fields = dict(re.findall(r'(\w+)="([^"]*)"', headers["authorization"]))
    checked = dict(headers)
    checked["x-content-sha256"] = base64.b64encode(hashlib.sha256(body).digest()).decode()
    checked["content-length"] = str(len(body))
    checked["(request-target)"] = "post " + path
    message = "\n".join(name + ": " + checked[name] for name in fields["headers"].split()).encode()
    public_key.verify(base64.b64decode(fields["signature"]), message, padding.PKCS1v15(), hashes.SHA256())

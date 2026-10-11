"""Synthetic native Chat inputs shared only by signing unit suites."""

import json
from types import SimpleNamespace

REGION = "us-ashburn-1"
TENANCY = "ocid1.tenancy.oc1..synthetic"
COMPARTMENT = "ocid1.compartment.oc1..synthetic"
MODEL = "google.gemini-2.5-flash-lite"


def chat_body(**overrides):
    value = {"compartmentId": COMPARTMENT,
             "servingMode": {"servingType": "ON_DEMAND", "modelId": MODEL},
             "chatRequest": {"apiFormat": "GENERIC", "maxTokens": 256,
                             "messages": [{"role": "USER", "content": [
                                 {"type": "TEXT", "text": "Classify a synthetic request."}]}]}}
    value.update(overrides)
    return json.dumps(value).encode()


class CallableIdentity:
    tenancy_id = TENANCY
    region = REGION

    def __init__(self):
        self.calls = []

    def __call__(self, request, enforce_content_headers=True):
        self.calls.append((request, enforce_content_headers))
        request.headers.update({"authorization": "Signature synthetic",
                                "host": request.url.split("/")[2],
                                "date": "Sat, 10 Oct 2026 12:00:00 GMT",
                                "x-content-sha256": "synthetic-digest"})
        return request


def sdk(identity):
    from unittest.mock import Mock
    return SimpleNamespace(__version__="2.187.0", retry=SimpleNamespace(NoneRetryStrategy=Mock()),
                           auth=SimpleNamespace(signers=SimpleNamespace(
                               InstancePrincipalsSecurityTokenSigner=Mock(return_value=identity))))

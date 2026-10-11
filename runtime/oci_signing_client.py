"""LiteLLM signer adapter with no SDK, metadata or credential access."""

import base64
import hashlib

from .gateway_http import GatewayError
from .oci_instance_signer import SIGNED_HEADERS
from .oci_signing_protocol import SIGNING_SOCKET, decode_reply, exchange
from .oci_signing_scope import SigningRejected, SigningScope


def _headers(value):
    if not isinstance(value, dict):
        raise ValueError
    normalized = {}
    for key, item in value.items():
        if (not isinstance(key, str) or key.lower() in normalized
                or not isinstance(item, str) or not 0 < len(item) <= 32768
                or any(ord(c) < 32 or ord(c) > 126 for c in item)):
            raise ValueError
        normalized[key.lower()] = item
    return normalized


class SocketSigner:
    def __init__(self, scope, *, path=SIGNING_SOCKET, timeout=30):
        if not isinstance(scope, SigningScope) or not 0 < timeout <= 30:
            raise SigningRejected("Invalid native signing client configuration")
        self.scope, self.path, self.timeout = scope, path, timeout

    def do_request_sign(self, request, enforce_content_headers=True):
        try:
            if (request.method != "POST" or request.url != self.scope.url
                    or enforce_content_headers is not True):
                raise ValueError
            body = self.scope.validate(request.body)
            before = _headers(request.headers)
            if (set(before) - {"content-type", "content-length", "user-agent"}
                    or before.get("content-type", "application/json") != "application/json"
                    or before.get("content-length", str(len(body))) != str(len(body))):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise SigningRejected("Native signing request rejected") from None
        try:
            reply = decode_reply(exchange(self.path, body, timeout=self.timeout))
            if reply == {"status": "rejected"}:
                raise SigningRejected("Native signing request rejected")
            if not isinstance(reply, dict) or set(reply) != {"status", "headers"} or reply["status"] != "ok":
                raise ValueError
            signed = _headers(reply["headers"])
            if (set(signed) != SIGNED_HEADERS or signed["host"] != self.scope.host
                    or signed["content-type"] != "application/json"
                    or signed["content-length"] != str(len(body))
                    or not signed["authorization"].startswith("Signature ")
                    or signed["x-content-sha256"] != base64.b64encode(hashlib.sha256(body).digest()).decode()):
                raise ValueError
        except SigningRejected:
            raise
        except (GatewayError, ValueError, TypeError, RecursionError):
            raise GatewayError("Native signing unavailable") from None
        request.headers.clear()
        request.headers.update(before | signed)
        return request

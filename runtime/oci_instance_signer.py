"""Host-only, serialized SDK signing; no inference transport or credential files."""

import os
import re
from threading import current_thread, main_thread
from types import SimpleNamespace

from .gateway_http import GatewayError, request_deadline
from .oci_signing_scope import CHAT_PATH, SigningScope
from .runtime_bundle import SETTINGS_PATTERNS

SDK_VERSION = "2.187.0"
METADATA_URL = "http://169.254.169.254/opc/v2"
SIGNED_HEADERS = frozenset({"authorization", "date", "host", "content-type", "content-length", "x-content-sha256"})


class SigningUnavailable(GatewayError):
    """An identity failure requires its owning service process to restart."""


def _load_sdk():
    import oci
    return oci


class InstanceSigner:
    def __init__(self, scope, tenancy_id, hosting_region):
        if not isinstance(scope, SigningScope):
            raise SigningUnavailable("Invalid instance signing configuration")
        for name, value in (("tenancy_ocid", tenancy_id), ("region", hosting_region)):
            if (not isinstance(value, str) or len(value) > 512
                    or re.fullmatch(SETTINGS_PATTERNS[name], value) is None):
                raise SigningUnavailable("Invalid instance signing configuration")
        self.scope, self.tenancy_id, self.hosting_region = scope, tenancy_id, hosting_region
        self._signer = None
        self._failed = False

    def _initialize(self):
        if os.environ.get("OCI_METADATA_BASE_URL", METADATA_URL) != METADATA_URL:
            raise ValueError
        # Dedicated host process only: never let SDK select another metadata URL.
        os.environ["OCI_METADATA_BASE_URL"] = METADATA_URL
        sdk = _load_sdk()
        if sdk.__version__ != SDK_VERSION:
            raise ValueError
        signer = sdk.auth.signers.InstancePrincipalsSecurityTokenSigner(
            retry_strategy=sdk.retry.NoneRetryStrategy(),
            federation_client_retry_strategy=sdk.retry.NoneRetryStrategy(),
            log_requests=False,
        )
        if signer.tenancy_id != self.tenancy_id or signer.region != self.hosting_region:
            raise ValueError
        self._signer = signer

    def sign(self, body, *, timeout=20):
        # Entire refresh-plus-sign operation belongs to one Unix main thread.
        # Another thread cannot even invalidate this owner's cached identity.
        if current_thread() is not main_thread():
            raise SigningUnavailable("Instance signing requires its dedicated main-thread service")
        if self._failed:
            raise SigningUnavailable("Instance signing unavailable; restart the signing service")
        self.scope.validate(body)
        try:
            with request_deadline(timeout):
                if self._signer is None:
                    self._initialize()
                request = SimpleNamespace(method="POST", url=self.scope.url, path_url=CHAT_PATH,
                                          body=body, headers={"content-type": "application/json",
                                                              "content-length": str(len(body))})
                # Callable invocation is essential: do_request_sign skips refresh.
                self._signer(request, enforce_content_headers=True)
                headers = dict(request.headers)
                if (set(headers) != SIGNED_HEADERS or request.body is not body
                        or headers["host"] != self.scope.host
                        or headers["content-type"] != "application/json"
                        or headers["content-length"] != str(len(body))
                        or any(not isinstance(value, str) or not 0 < len(value) <= 32768
                               or any(ord(c) < 32 or ord(c) > 126 for c in value)
                               for value in headers.values())):
                    raise ValueError
                return headers
        except Exception:
            # SDK exceptions can contain private metadata. Never echo or chain.
            # Refresh may have rotated keys already: do not reuse or retry here.
            self._failed = True
            raise SigningUnavailable("Instance signing unavailable; restart the signing service") from None

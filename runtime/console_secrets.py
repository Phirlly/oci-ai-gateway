"""Host-only CURRENT reads for the three exact Console deployment secrets."""

import base64
import json
import os
import subprocess
from dataclasses import dataclass

from .cloud_credentials import OCI
from .console_settings import is_ocid, provider_secrets, runtime_settings, validate_console_settings
from .gateway_http import GatewayError


@dataclass(frozen=True, repr=False)
class Secret:
    content: bytes
    version: int
    identifier: str


def read_secret(settings, *, secret_id=None, context=False):
    settings = validate_console_settings(settings)
    if context:
        if secret_id is not None:
            raise GatewayError("Ambiguous Console secret selection")
        selection = ["get-secret-bundle-by-name", "--vault-id", settings["vault_ocid"],
                     "--secret-name", settings["context_name"]]
    else:
        if secret_id not in {*provider_secrets(settings).values(), settings["presenter_secret_ocid"]}:
            raise GatewayError("Unrecognized Console secret selection")
        selection = ["get", "--secret-id", secret_id]
    command = [OCI, "--config-file", "/dev/null", "--cli-rc-file", "/dev/null", "--auth", "instance_principal",
               "--region", runtime_settings(settings)["region"], "--output", "json", "--query", "@", "--no-retry",
               "--enable-propagation", "False", "--connection-timeout", "5", "--read-timeout", "20",
               "secrets", "secret-bundle", *selection, "--stage", "CURRENT"]
    environment = {key: value for key, value in os.environ.items()
                   if key in {"HOME", "PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR"}}
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                timeout=45, env=environment, stdin=subprocess.DEVNULL)
        if result.returncode or len(result.stdout) > 65536:
            raise ValueError
        # The outer CLI envelope may be larger than the bounded decoded content.
        data = json.loads(result.stdout)["data"]
        if (not is_ocid(data["secret-id"], "vaultsecret")
                or (not context and data["secret-id"] != secret_id)
                or not isinstance(data["stages"], list) or "CURRENT" not in data["stages"]
                or type(data["version-number"]) is not int or data["version-number"] < 1
                or data["secret-bundle-content"]["content-type"] != "BASE64"):
            raise ValueError
        content = base64.b64decode(data["secret-bundle-content"]["content"], validate=True)
        if len(content) > 16384:
            raise ValueError
        return Secret(content, data["version-number"], data["secret-id"])
    except (OSError, UnicodeError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError, RecursionError):
        raise GatewayError("Console CURRENT secret read unavailable; check IAM and secret versions") from None

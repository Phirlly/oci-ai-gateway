"""Create internal credentials once; refresh only the external provider key."""

import secrets

from .console_state import read_record, write_record
from .gateway_http import GatewayError

INTERNAL = {"database_password", "gateway_master_key", "gateway_salt_key"}


def internal_credentials(directory):
    value = read_record(directory, "console-credentials.json")
    if value is None:
        value = {key: ("sk-" if key == "gateway_master_key" else "") + secrets.token_hex(32)
                 for key in sorted(INTERNAL)}
        write_record(directory, "console-credentials.json", value)
    if (not isinstance(value, dict) or set(value) != INTERNAL
            or any(not isinstance(item, str) or not 64 <= len(item) <= 67
                   or any(c not in "0123456789abcdefsk-" for c in item) for item in value.values())):
        raise GatewayError("Internal credentials changed; preserve them for recovery")
    return value


def publish_credentials(directory, value):
    internal = internal_credentials(directory)
    if (not isinstance(value, dict) or set(value) != INTERNAL | {"external_api_key"}
            or any(value[key] != internal[key] for key in INTERNAL)
            or not isinstance(value["external_api_key"], str) or not 1 <= len(value["external_api_key"]) <= 8192
            or any(ord(c) < 33 or ord(c) > 126 for c in value["external_api_key"])):
        raise GatewayError("Invalid Console credential refresh")
    previous = read_record(directory, "gateway-secrets.json")
    if previous is not None and (not isinstance(previous, dict) or set(previous) != set(value)
                                 or any(previous[key] != internal[key] for key in INTERNAL)):
        raise GatewayError("Gateway internal credentials changed; preserve them for recovery")
    if previous != value:
        write_record(directory, "gateway-secrets.json", value)

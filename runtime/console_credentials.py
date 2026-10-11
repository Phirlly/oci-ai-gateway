"""Create internal credentials once; refresh only the external provider key."""

import secrets

from .console_state import read_record, write_record
from .console_settings import decode_json, provider_secrets
from .gateway_http import GatewayError
from .password_policy import valid_presenter_password

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


def publish_credentials(directory, value, *, required_keys=None):
    internal = internal_credentials(directory)
    required_keys = {"external_api_key"} if required_keys is None else required_keys
    if (not isinstance(required_keys, set) or not required_keys <= {"external_api_key", "anthropic_api_key", "openai_api_key"}
            or not isinstance(value, dict) or set(value) != INTERNAL | required_keys
            or any(value[key] != internal[key] for key in INTERNAL)
            or any(not isinstance(value[key], str) or not 1 <= len(value[key]) <= 8192
                   or any(ord(c) < 33 or ord(c) > 126 for c in value[key]) for key in required_keys)):
        raise GatewayError("Invalid Console credential refresh")
    previous = read_record(directory, "gateway-secrets.json")
    if previous is not None and (not isinstance(previous, dict) or set(previous) != set(value)
                                 or any(previous[key] != internal[key] for key in INTERNAL)):
        raise GatewayError("Gateway internal credentials changed; preserve them for recovery")
    if previous != value:
        write_record(directory, "gateway-secrets.json", value)


def console_inputs(settings, read_secret):
    """Read and validate the complete selection before publishing any credentials."""
    optional = settings["schema_version"] == 2
    selected = {p: read_secret(settings, secret_id=identifier)
                for p, identifier in provider_secrets(settings).items()}
    if any(secret.content == b"UNCONFIGURED" for secret in selected.values()):
        return None
    try:
        password = decode_json(read_secret(settings, secret_id=settings["presenter_secret_ocid"]).content)
        if (not isinstance(password, dict) or set(password) != {"password"}
                or not valid_presenter_password(password["password"])):
            raise ValueError
        keys = {(p + "_api_key" if optional else "external_api_key"): secret.content.decode("ascii")
                for p, secret in selected.items()}
        if any(not 1 <= len(key) <= 8192 or any(ord(c) < 33 or ord(c) > 126 for c in key) for key in keys.values()):
            raise ValueError
        if optional and any(read_secret(settings, secret_id=provider_secrets(settings)[p]) != secret
                            for p, secret in selected.items()):
            raise GatewayError("Selected keys changed while reading; retry preparation")
        versions = {p: secret.version for p, secret in selected.items()}
        return keys, password["password"], versions if optional else versions["anthropic"]
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise GatewayError("Console credential format is invalid") from None

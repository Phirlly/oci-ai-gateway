"""Console settings and nonsecret context; no controller bundle or stack identity."""

import json
import re
from ipaddress import IPv4Address

from .gateway_http import GatewayError
from .runtime_bundle import validate_settings


def decode_json(content):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON field")
            value[key] = item
        return value
    if not isinstance(content, bytes) or len(content) > 16384:
        raise ValueError("Console document exceeds its budget")
    return json.loads(content, object_pairs_hook=unique)


def is_ocid(value, kind):
    return (isinstance(value, str) and len(value) <= 512
            and re.fullmatch(r"ocid1\." + kind + r"\.oc1\.[a-z0-9-]+\.[a-zA-Z0-9._-]+", value) is not None)


def validate_console_settings(value):
    try:
        optional = isinstance(value, dict) and value.get("schema_version") == 2
        runtime_key = "runtime" if optional else "native"
        fields = {"schema_version", runtime_key, "vault_ocid", "presenter_secret_ocid", "context_name"}
        if optional:
            fields.add("provider_secrets")
        if (not isinstance(value, dict) or set(value) != fields
                or type(value["schema_version"]) is not int or value["schema_version"] not in (1, 2)
                or not is_ocid(value["vault_ocid"], "vault")
                or not is_ocid(value["presenter_secret_ocid"], "vaultsecret")):
            raise ValueError
        native = validate_settings(value[runtime_key])
        if (native["schema_version"] != (4 if optional else 3) or value["context_name"] != native["deployment_id"] + "-context"
                or value["presenter_secret_ocid"] == native["secret_ocid"]):
            raise ValueError
        if optional:
            secrets = value["provider_secrets"]
            if (not isinstance(secrets, dict) or set(secrets) != set(native["models"]) - {"oci"}
                    or any(not is_ocid(item, "vaultsecret") for item in secrets.values())
                    or len(set(secrets.values())) != len(secrets)
                    or set(secrets.values()) & {value["presenter_secret_ocid"], native["secret_ocid"]}):
                raise ValueError
        return {**value, runtime_key: native}
    except (ValueError, KeyError, TypeError):
        raise GatewayError("Invalid Console deployment settings") from None


def runtime_settings(settings):
    return settings["runtime" if settings["schema_version"] == 2 else "native"]


def provider_secrets(settings):
    return settings["provider_secrets"] if settings["schema_version"] == 2 else {"anthropic": settings["native"]["secret_ocid"]}


def load_context(content, settings, instance_id):
    settings = validate_console_settings(settings)
    try:
        value = decode_json(content)
        if (not isinstance(value, dict) or set(value) != {"schema_version", "settings", "instance_ocid",
                "public_ip_ocid", "public_ip", "verification_run"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["settings"] != settings or not is_ocid(instance_id, "instance")
                or value["instance_ocid"] != instance_id or not is_ocid(value["public_ip_ocid"], "publicip")
                or type(value["verification_run"]) is not int or not 1 <= value["verification_run"] <= 20):
            raise ValueError
        address = IPv4Address(value["public_ip"])
        if str(address) != value["public_ip"] or not address.is_global or address.is_multicast:
            raise ValueError
        return value
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise GatewayError("Console context is invalid or belongs to another deployment") from None

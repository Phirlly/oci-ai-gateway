"""Validate schema4 runtime ownership and only the selected provider credentials."""

import re
from ipaddress import IPv4Address
from types import MappingProxyType

from .gateway_http import GatewayError
from .password_policy import valid_presenter_password
from .presenter import Presenter
from .provider_selection import model_aliases, provider_keys

INTERNAL_FIELDS = {"database_password", "gateway_master_key", "gateway_salt_key", "demo_password"}
RUNTIME_FIELDS = {"public_ip", "public_ip_ocid", "instance_ocid", "presenter_email"}


def valid_credential_value(value):
    return (isinstance(value, str) and 0 < len(value) <= 8192
            and all(32 <= ord(c) < 127 for c in value))


def valid_credentials(value, settings):
    return (isinstance(value, dict) and set(value) == INTERNAL_FIELDS | provider_keys(settings)
            and all(valid_credential_value(item) for key, item in value.items() if key != "demo_password")
            and valid_presenter_password(value["demo_password"]))


def load_optional_bundle(value, settings, instance_id):
    from .runtime_bundle import RuntimeBundle, _ocid
    try:
        identity = {key: item for key, item in settings.items()
                    if key not in {"schema_version", "region", "presenter_email"}}
        identity["stack_ocid"] = value["identity"]["stack_ocid"]
        if (set(value) != {"schema_version", "kind", "identity", "operation_id", "runtime", "credentials"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 4
                or value["kind"] != "runtime-bundle" or value["identity"] != identity
                or not _ocid(identity["stack_ocid"], "ormstack")
                or not isinstance(value["operation_id"], str)
                or re.fullmatch(r"[a-f0-9]{32}", value["operation_id"]) is None
                or not isinstance(value["runtime"], dict) or set(value["runtime"]) != RUNTIME_FIELDS
                or not valid_credentials(value["credentials"], settings)):
            raise ValueError
        context = value["runtime"]
        address = IPv4Address(context["public_ip"])
        if (context["instance_ocid"] != instance_id or not _ocid(instance_id, "instance")
                or context["presenter_email"] != settings["presenter_email"]
                or not _ocid(context["public_ip_ocid"], "publicip")
                or str(address) != context["public_ip"] or not address.is_global or address.is_multicast):
            raise ValueError
        presenter = Presenter(settings["deployment_id"], settings["presenter_email"], model_aliases(settings))
        return RuntimeBundle(MappingProxyType(settings), str(address),
                             MappingProxyType(dict(value["credentials"])), presenter)
    except (ValueError, TypeError, KeyError):
        raise GatewayError("Optional-provider bundle is invalid or belongs to another deployment") from None

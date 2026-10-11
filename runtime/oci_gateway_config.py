"""Read fixed native signing authority from the gateway's existing configuration."""

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from .gateway_http import GatewayError
from .oci_signing_scope import SigningScope
from .runtime_bundle import MODEL_ALIASES

GATEWAY_CONFIG = Path("/app/config.json")
NATIVE_PARAMS = {"model", "oci_region", "oci_compartment_id", "additional_drop_params",
                 "max_tokens", "num_retries"}
INVALID_CONFIG = "Native gateway configuration is invalid"


@dataclass(frozen=True)
class GatewayRoutes:
    scope: SigningScope | None
    external_model: str | None
    openai_model: str | None = None

    @property
    def aliases(self):
        return tuple(alias for alias, enabled in (
            (MODEL_ALIASES[0], self.scope), (MODEL_ALIASES[1], self.external_model),
            ("external-openai", self.openai_model)) if enabled is not None)


def _external(params, provider):
    if (not isinstance(params, dict) or set(params) != {"model", "api_key"}
            or params["api_key"] != "os.environ/" + provider.upper() + "_API_KEY"
            or not isinstance(params["model"], str)
            or re.fullmatch(provider + r"/[a-zA-Z0-9][a-zA-Z0-9._:-]{0,254}", params["model"]) is None):
        raise ValueError
    return params["model"]


def _native(native):
    if (not isinstance(native, dict) or set(native) != NATIVE_PARAMS
            or not isinstance(native["model"], str) or not native["model"].startswith("oci/")
            or native["additional_drop_params"] != ["stream_options"]
            or type(native["num_retries"]) is not int or native["num_retries"] != 0
            or type(native["max_tokens"]) is not int or not 1 <= native["max_tokens"] <= 4096):
        raise ValueError
    return SigningScope(native["oci_region"], native["oci_compartment_id"], native["model"][4:])


def parse_routes(value):
    try:
        rows = value["model_list"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 3:
            raise ValueError
        routes = {row["model_name"]: row["litellm_params"] for row in rows}
        if len(routes) != len(rows) or not set(routes) <= {*MODEL_ALIASES, "external-openai"}:
            raise ValueError
        scope = _native(routes[MODEL_ALIASES[0]]) if MODEL_ALIASES[0] in routes else None
        anthropic = _external(routes[MODEL_ALIASES[1]], "anthropic") if MODEL_ALIASES[1] in routes else None
        openai = _external(routes["external-openai"], "openai") if "external-openai" in routes else None
        return GatewayRoutes(scope, anthropic, openai)
    except (GatewayError, ValueError, TypeError, KeyError):
        raise GatewayError(INVALID_CONFIG) from None


def _unique(pairs):
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError
        value[name] = item
    return value


def load_routes(path=None):
    """Startup-only read; no second settings file, credentials or network access."""
    try:
        descriptor = os.open(GATEWAY_CONFIG if path is None else path,
                             os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
                    or metadata.st_mode & 0o077 or metadata.st_size > 32768):
                raise ValueError
            body = stream.read(32769)
        if len(body) > 32768:
            raise ValueError
        return parse_routes(json.loads(body, object_pairs_hook=_unique))
    except (OSError, ValueError, TypeError, RecursionError):
        raise GatewayError(INVALID_CONFIG) from None

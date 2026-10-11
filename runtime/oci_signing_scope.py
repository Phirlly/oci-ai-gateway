"""Authorize one bounded native Chat body, without accepting signing headers."""

import json
import math
import re
from dataclasses import dataclass

from .gateway_http import GatewayError
from .runtime_bundle import SETTINGS_PATTERNS

MAX_SIGNING_BODY = 256 * 1024
CHAT_PATH = "/20231130/actions/chat"


class SigningRejected(GatewayError):
    """The caller's request is outside the configured signing scope."""


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError
        value[key] = item
    return value


def _finite_tree(value, depth=0):
    if depth > 32 or isinstance(value, float) and not math.isfinite(value):
        raise ValueError
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif isinstance(value, dict):
        for key, item in value.items():
            _finite_tree(key, depth + 1)
            _finite_tree(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _finite_tree(item, depth + 1)


@dataclass(frozen=True)
class SigningScope:
    region: str
    compartment_id: str
    model_id: str

    def __post_init__(self):
        for name, value in (("region", self.region), ("compartment_ocid", self.compartment_id),
                            ("model_id", self.model_id)):
            if (not isinstance(value, str) or len(value) > 512
                    or re.fullmatch(SETTINGS_PATTERNS[name], value) is None):
                raise SigningRejected("Invalid native signing configuration")

    @property
    def host(self):
        return "inference.generativeai." + self.region + ".oci.oraclecloud.com"

    @property
    def url(self):
        return "https://" + self.host + CHAT_PATH

    def validate(self, body):
        try:
            if type(body) is not bytes or not 0 < len(body) <= MAX_SIGNING_BODY:
                raise ValueError
            value = json.loads(body.decode("utf-8", errors="strict"), object_pairs_hook=_unique)
            _finite_tree(value)
            if (not isinstance(value, dict) or set(value) != {"compartmentId", "servingMode", "chatRequest"}
                    or value["compartmentId"] != self.compartment_id
                    or value["servingMode"] != {"servingType": "ON_DEMAND", "modelId": self.model_id}):
                raise ValueError
            chat = value["chatRequest"]
            if (not isinstance(chat, dict) or chat.get("apiFormat") != "GENERIC"
                    or type(chat.get("maxTokens")) is not int or not 1 <= chat["maxTokens"] <= 4096):
                raise ValueError
            return body
        except (ValueError, TypeError, RecursionError):
            raise SigningRejected("Native signing request rejected") from None

"""Versioned complete settings for the supported two-provider CPU deployment."""

import json
import re
from copy import deepcopy
from types import MappingProxyType

from runtime.gateway_http import GatewayError
from runtime.provider_selection import validate_models

from .credential_errors import DeliveryError
from .deployment_config import FoundationConfig, PATTERNS

TEXT_PATTERNS = {
    "inference_region": PATTERNS["region"],
    "external_provider": r"anthropic",
    "external_model_id": r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}",
    "presenter_email": r"[a-zA-Z0-9._+%-]{1,64}@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+",
    "instance_shape": r"VM\.Standard\.E[45]\.Flex",
    "image_name": r"Canonical-Ubuntu-24\.04-\d{4}\.\d{2}\.\d{2}-\d+",
}
# Deliberate demo bounds, narrower than OCI's service limits.
INTEGER_LIMITS = {
    "schema_version": (2, 2),
    "instance_ocpus": (1, 16),
    "instance_memory_gbs": (8, 256),
    "boot_volume_size_gbs": (50, 500),
    "availability_domain_number": (1, 3),
    "model_key_ttl_days": (1, 30),
}


class GatewayConfig(FoundationConfig):
    def __init__(self, values):
        object.__setattr__(self, "_settings", deepcopy(values))
        self.__post_init__()

    @property
    def values(self):
        """Return a snapshot; callers cannot mutate nested deployment identity."""
        return MappingProxyType(deepcopy(self._settings))

    @property
    def is_native(self):
        return self.values["schema_version"] in (3, 4)

    @property
    def is_optional(self):
        return self.values["schema_version"] == 4

    def __post_init__(self):
        try:
            value = deepcopy(self._settings)
            native = isinstance(value, dict) and value.get("schema_version") in (3, 4)
            optional = isinstance(value, dict) and value.get("schema_version") == 4
            limits = dict(INTEGER_LIMITS)
            patterns = PATTERNS | TEXT_PATTERNS
            if native:
                limits["schema_version"] = (value["schema_version"], value["schema_version"])
                del limits["model_key_ttl_days"]
            if optional:
                value["models"] = validate_models(value.get("models"))
                for field in ("oci_model_id", "external_provider", "external_model_id"):
                    del patterns[field]
                if "oci" not in value["models"]:
                    del patterns["inference_region"]
            if not isinstance(value, dict) or set(value) != set(patterns) | set(limits) | ({"models"} if optional else set()):
                raise ValueError
            for name, pattern in patterns.items():
                item = value[name]
                if not isinstance(item, str) or len(item) > 255 or re.fullmatch(pattern, item) is None:
                    raise ValueError
            for name, (low, high) in limits.items():
                item = value[name]
                if type(item) is not int or not low <= item <= high:
                    raise ValueError
            if not value["instance_ocpus"] <= value["instance_memory_gbs"] <= 64 * value["instance_ocpus"]:
                raise ValueError
        except (KeyError, TypeError, ValueError, GatewayError):
            raise DeliveryError("Invalid gateway settings; use version4 or retain original version2/3 settings for recovery.") from None
        object.__setattr__(self, "_settings", dict(value))

    def orm_variables(self, *, model_key_ocid):
        if self.is_native and model_key_ocid is not None:
            raise DeliveryError("Native deployment cannot carry a model-key binding.")
        values = super().orm_variables(model_key_ocid=model_key_ocid)
        return {key: json.dumps(value, sort_keys=True, separators=(",", ":")) if type(value) in (int, dict) else value
                for key, value in values.items()}

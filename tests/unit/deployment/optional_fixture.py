"""Schema4 deployment inputs with no fabricated native scope."""

from tests.unit.runtime.optional_fixture import MODELS
from .native_fixture import NATIVE_SETTINGS


def settings(providers=tuple(MODELS)):
    value = {key: item for key, item in NATIVE_SETTINGS.items()
             if key not in {"oci_model_id", "external_provider", "external_model_id", "inference_region"}}
    value.update(schema_version=4, models={name: MODELS[name] for name in providers})
    if "oci" in providers:
        value["inference_region"] = "us-ashburn-1"
    return value

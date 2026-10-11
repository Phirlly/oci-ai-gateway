"""The three supported provider slots and their explicit credential boundaries."""

import re

from .gateway_http import GatewayError

ALIASES = {"oci": "oci-managed", "anthropic": "external-anthropic", "openai": "external-openai"}
MODEL_PATTERN = r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,254}"


def validate_models(value):
    if (not isinstance(value, dict) or not value or not set(value) <= set(ALIASES)
            or any(not isinstance(model, str) or re.fullmatch(MODEL_PATTERN, model) is None
                   for model in value.values())):
        raise GatewayError("Select at least one supported provider and a valid model ID")
    return {provider: value[provider] for provider in ALIASES if provider in value}


def model_aliases(settings):
    return tuple(ALIASES[p] for p in validate_models(settings["models"]))


def provider_keys(settings):
    return {p + "_api_key" for p in validate_models(settings["models"]) if p != "oci"}


def model_routes(settings):
    rows = []
    for provider, model in validate_models(settings["models"]).items():
        alias = ALIASES[provider]
        params = {"model": provider + "/" + model}
        if provider == "oci":
            params.update(oci_region=settings["inference_region"],
                          oci_compartment_id=settings["compartment_ocid"],
                          additional_drop_params=["stream_options"], max_tokens=256, num_retries=0)
        else:
            params["api_key"] = "os.environ/" + provider.upper() + "_API_KEY"
        rows.append({"model_name": alias, "model_info": {"id": alias, "mode": "chat"},
                     "litellm_params": params})
    return rows

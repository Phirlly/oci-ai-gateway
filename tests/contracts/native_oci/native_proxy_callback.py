"""Test-owned route setup and HTTP transport; not deployed gateway policy."""

from litellm.integrations.custom_logger import CustomLogger
from fastapi import HTTPException

from payload_fixture import COMPARTMENT, MODEL, ROUTE
from native_proxy_upstream import NativeUpstream

FORBIDDEN = frozenset({
    "api_base", "base_url", "api_key", "custom_llm_provider", "client",
    "extra_headers", "headers", "default_headers", "extra_body",
    "router_settings", "user_config", "litellm_params", "fallbacks", "num_retries",
    "model_list", "credential_name", "litellm_credential_name",
    "provider_specific_header", "router_settings_override", "drop_params",
    "additional_drop_params", "allowed_openai_params",
    "model_group_retry_policy", "litellm_request_debug",
})


def reject():
    raise HTTPException(400, "Native route overrides are not permitted")


class NativeProbe(CustomLogger):
    def __init__(self):
        super().__init__()
        self.upstream = NativeUpstream()
        self.oci_signer = None  # The socket fixture supplies the production client.

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        snapshot = data.get("proxy_server_request", {})
        fields = set(data) | set(snapshot.get("credential_fields", ()))
        fields.update(snapshot.get("body", {}))
        if (data.get("model") != ROUTE or fields & FORBIDDEN
                or any(name.startswith("oci_") for name in fields)):
            reject()
        # Native OCI does not forward usage. Do not ask the shared wrapper to
        # manufacture a usage chunk from local token estimates.
        data.pop("stream_options", None)
        return data

    async def async_pre_call_deployment_hook(self, kwargs, call_type):
        if (kwargs.get("model") != "oci/" + MODEL
                or kwargs.get("oci_region") != "us-ashburn-1"
                or kwargs.get("oci_compartment_id") != COMPARTMENT
                or kwargs.get("custom_llm_provider") not in (None, "oci")
                or any(kwargs.get(name) is not None for name in
                       ("api_base", "base_url", "api_key", "extra_body", "oci_signer"))):
            reject()
        kwargs["client"] = self.upstream.handler
        kwargs["oci_signer"] = self.oci_signer
        # Proxy logging is initialized before pre-call hooks. Clear its earlier
        # stream_options snapshot as well as the incoming request option.
        kwargs["litellm_logging_obj"].stream_options = None
        return kwargs


INSTANCE = NativeProbe()

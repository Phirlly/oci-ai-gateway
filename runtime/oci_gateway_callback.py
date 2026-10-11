"""Restrict the two gateway routes and attach the private native OCI signer."""

from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger

from runtime.oci_gateway_config import GatewayRoutes
from runtime.oci_signing_client import SocketSigner
from runtime.runtime_bundle import MODEL_ALIASES

FORBIDDEN = frozenset({
    "api_base", "base_url", "api_key", "custom_llm_provider", "client",
    "extra_headers", "headers", "default_headers", "extra_body",
    "router_settings", "user_config", "litellm_params", "fallbacks", "num_retries",
    "model_list", "credential_name", "litellm_credential_name",
    "provider_specific_header", "router_settings_override", "drop_params",
    "additional_drop_params", "allowed_openai_params", "model_group_retry_policy",
    "litellm_request_debug", "mock_response", "mock_tool_calls", "mock_timeout",
    "mock_testing_fallbacks", "timeout", "max_retries",
    "context_window_fallbacks", "content_policy_fallbacks",
})


def reject():
    raise HTTPException(400, "Gateway route overrides are not permitted")


class NativeGateway(CustomLogger):
    def __init__(self, routes: GatewayRoutes):
        super().__init__()
        self.routes = routes
        self.oci_signer = SocketSigner(routes.scope)

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        snapshot = data.get("proxy_server_request")
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("body"), dict):
            reject()
        credentials = snapshot.get("credential_fields", ())
        if not isinstance(credentials, (tuple, list)) or any(not isinstance(k, str) for k in credentials):
            reject()
        fields = set(data) | set(snapshot["body"]) | set(credentials)
        # CLI request_timeout is injected after this snapshot; reject caller input only.
        if ("request_timeout" in snapshot["body"]
                or data.get("model") not in MODEL_ALIASES or fields & FORBIDDEN
                or any(not isinstance(k, str) or k.startswith("oci_") for k in fields)):
            reject()
        if data["model"] == MODEL_ALIASES[0]:
            # Native streaming usage is unavailable; do not emit local estimates.
            data.pop("stream_options", None)
        return data

    async def async_pre_call_deployment_hook(self, kwargs, call_type):
        scope = self.routes.scope
        model = kwargs.get("model")
        if model == self.routes.external_model:
            if (any(k.startswith("oci_") for k in kwargs)
                    or kwargs.get("custom_llm_provider") not in (None, "anthropic")
                    or any(kwargs.get(k) is not None for k in ("api_base", "base_url", "extra_body"))):
                reject()
            return kwargs
        if (model != "oci/" + scope.model_id
                or kwargs.get("oci_region") != scope.region
                or kwargs.get("oci_compartment_id") != scope.compartment_id
                or kwargs.get("custom_llm_provider") not in (None, "oci")
                or any(k.startswith("oci_") and k not in {"oci_region", "oci_compartment_id"} for k in kwargs)
                or any(kwargs.get(k) is not None for k in ("api_base", "base_url", "api_key", "extra_body"))):
            reject()
        kwargs["oci_signer"] = self.oci_signer
        # The proxy initializes logging before admission; clear that copy too.
        kwargs["litellm_logging_obj"].stream_options = None
        return kwargs

"""Requests cannot change routing, retries, parameter validation or debug policy."""

from admission_fixture import AdmissionCase
from payload_fixture import COMPARTMENT, MODEL, ROUTE
from native_proxy_fixture import EXTERNAL
from demo.results import completion


class GatewayExecutionControls(AdmissionCase):
    async def test_conditional_fallbacks_cannot_switch_the_selected_route(self):
        self.upstream.mode = "context_error"
        for name in ("context_window_fallbacks", "content_policy_fallbacks"):
            with self.subTest(field=name):
                await self.deny({name: [{EXTERNAL: [ROUTE]}, {ROUTE: [EXTERNAL]}]})

    async def test_body_router_and_retry_overrides_are_denied(self):
        for name, value in (("router_settings", {"num_retries": 8}),
                            ("router_settings_override", {"num_retries": 1}),
                            ("model_group_retry_policy", {ROUTE: {"DefaultRetries": 1}}),
                            ("litellm_params", {"api_base": "https://synthetic.invalid"}),
                            ("extra_body", {"compartmentId": "ocid1.compartment.oc1..other"}),
                            ("fallbacks", ["other"]), ("num_retries", 8),
                            ("request_timeout", 600), ("timeout", 600), ("max_retries", 8)):
            await self.deny({name: value})

    async def test_validation_and_debug_overrides_are_denied(self):
        for name, value in (("drop_params", True), ("additional_drop_params", ["top_logprobs"]),
                            ("allowed_openai_params", ["top_logprobs"]), ("litellm_request_debug", True),
                            ("mock_testing_fallbacks", True)):
            await self.deny({name: value})

    async def test_proxy_strips_caller_mock_and_runs_the_actual_adapters(self):
        for alias in (ROUTE, EXTERNAL):
            with self.subTest(alias=alias):
                before = len(self.upstream.requests)
                response = await self.request({"model": alias, "mock_response": "FORGED"})
                self.assertEqual(completion(self.result(response), alias)[0], "BILLING")
                self.assertEqual(len(self.upstream.requests), before + 1)
        self.assertEqual(len(self.socket.requests), 1)


class GatewayCallerRouter(AdmissionCase):
    allow_client_credentials = True

    async def test_neither_alias_can_install_a_caller_native_router(self):
        model_list = [{"model_name": ROUTE, "litellm_params": {
            "model": "oci/" + MODEL, "oci_region": "us-ashburn-1",
            "oci_compartment_id": COMPARTMENT, "additional_drop_params": ["top_logprobs"],
        }}]
        await self.deny({"user_config": {"model_list": model_list}, "top_logprobs": 2})
        await self.deny({"model_list": model_list})

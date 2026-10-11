"""Exact model parameter mapping and synthetic signing dispatch."""

import json
import unittest

from litellm.exceptions import UnsupportedParamsError
from litellm.llms.oci.chat.transformation import OCIChatConfig
from litellm.llms.oci.common_utils import OCIError
from litellm.utils import get_optional_params

from payload_fixture import COMPARTMENT, MODEL


class NativeRequests(unittest.TestCase):
    def test_compare_usage_option_requires_explicit_compatibility_setting(self):
        with self.assertRaises(OCIError):
            get_optional_params(model=MODEL, custom_llm_provider="oci", stream=True,
                                stream_options={"include_usage": True}, drop_params=False)

    def test_narrow_drop_keeps_streaming_and_output_limit(self):
        params = get_optional_params(
            model=MODEL, custom_llm_provider="oci", stream=True, max_tokens=32,
            stream_options={"include_usage": True}, additional_drop_params=["stream_options"],
            drop_params=False,
        )
        params["oci_compartment_id"] = COMPARTMENT
        payload = OCIChatConfig().transform_request(
            model=MODEL, messages=[{"role": "user", "content": "Synthetic request"}],
            optional_params=params, litellm_params={}, headers={},
        )
        self.assertEqual(payload["servingMode"], {"servingType": "ON_DEMAND", "modelId": MODEL})
        self.assertEqual(payload["compartmentId"], COMPARTMENT)
        self.assertEqual(payload["chatRequest"]["apiFormat"], "GENERIC")
        self.assertIs(payload["chatRequest"]["isStream"], True)
        self.assertEqual(payload["chatRequest"]["maxTokens"], 32)
        self.assertNotIn("streamOptions", payload["chatRequest"])

    def test_narrow_drop_does_not_hide_other_unsupported_options(self):
        with self.assertRaises(UnsupportedParamsError):
            get_optional_params(model=MODEL, custom_llm_provider="oci", top_logprobs=2,
                                additional_drop_params=["stream_options"], drop_params=False)

    def test_synthetic_signer_receives_exact_native_request(self):
        observed = []

        class RecordingSigner:
            def do_request_sign(self, request, enforce_content_headers=True):
                observed.append((request, enforce_content_headers))
                request.headers["authorization"] = "synthetic-signature"

        config = OCIChatConfig()
        params = {"oci_region": "us-ashburn-1", "oci_compartment_id": COMPARTMENT,
                  "oci_signer": RecordingSigner(), "maxTokens": 32}
        payload = config.transform_request(
            model=MODEL, messages=[{"role": "user", "content": "Synthetic request"}],
            optional_params=params, litellm_params={}, headers={},
        )
        url = config.get_complete_url(None, None, MODEL, params, {})
        headers, body = config.sign_request({}, params, payload, url, model=MODEL)
        self.assertEqual(len(observed), 1)
        request, enforce_content_headers = observed[0]
        self.assertTrue(enforce_content_headers)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url, "https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com/20231130/actions/chat")
        self.assertEqual(json.loads(request.body), payload)
        self.assertEqual(request.body, body)
        self.assertEqual(headers["authorization"], "synthetic-signature")


if __name__ == "__main__":
    unittest.main()

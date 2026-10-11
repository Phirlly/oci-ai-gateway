"""Successful terminal mappings and explicit native completion rejection."""

import unittest

import httpx
from litellm import ModelResponse
from litellm.llms.oci.chat.cohere import handle_cohere_response, handle_cohere_stream_chunk
from litellm.llms.oci.chat.generic import handle_generic_stream_chunk
from litellm.llms.oci.common_utils import OCIError

from payload_fixture import MODEL, ROUTE, USAGE, framed_completion, transformed_completion
from demo.results import completion


class NativeCompletionCorrection(unittest.TestCase):
    def test_uppercase_stop_preserves_completion_and_usage(self):
        result = transformed_completion("STOP")
        self.assertEqual(result.model, MODEL)
        self.assertEqual(result.choices[0].finish_reason, "stop")
        self.assertEqual(completion(framed_completion(result), ROUTE), ("BILLING", USAGE))

    def test_complete_length_and_tool_reasons_preserve_semantics(self):
        cases = {"COMPLETE": "stop", "stop": "stop", "MAX_TOKENS": "length",
                 "length": "length", "TOOL_CALL": "tool_calls", "TOOL_CALLS": "tool_calls",
                 "tool_calls": "tool_calls"}
        for reason, expected in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(transformed_completion(reason).choices[0].finish_reason, expected)

    def test_error_and_cancelled_completions_are_rejected_before_demo_parser(self):
        for reason in ("ERROR", "USER_CANCEL"):
            with self.subTest(reason=reason):
                with self.assertRaises(OCIError) as caught:
                    transformed_completion(reason)
                self.assertEqual(caught.exception.status_code, 502)

    def test_unknown_finish_is_rejected_without_echoing_provider_value(self):
        marker = "unexpected-sensitive-provider-value"
        with self.assertRaises(OCIError) as caught:
            transformed_completion(marker)
        self.assertEqual(caught.exception.status_code, 502)
        self.assertNotIn(marker, str(caught.exception))

    def test_completion_requires_final_reason(self):
        with self.assertRaises(OCIError):
            transformed_completion(None)

    def test_missing_reason_is_valid_for_an_intermediate_delta(self):
        chunk = handle_generic_stream_chunk({"index": 0, "message": {
            "role": "ASSISTANT", "content": [{"type": "TEXT", "text": "BILL"}],
        }})
        self.assertIsNone(chunk.choices[0].finish_reason)
        self.assertEqual(chunk.choices[0].delta.content, "BILL")

    def test_cohere_complete_length_and_tool_controls(self):
        for reason, expected in (("COMPLETE", "stop"), ("MAX_TOKENS", "length"),
                                 ("TOOL_CALLS", "tool_calls")):
            with self.subTest(reason=reason):
                body = {"modelId": MODEL, "modelVersion": "synthetic", "chatResponse": {
                    "apiFormat": "COHERE", "text": "BILLING", "finishReason": reason,
                }}
                result = handle_cohere_response(body, "cohere.command-a-03-2025", ModelResponse(),
                                                httpx.Response(200, json=body))
                self.assertEqual(result.choices[0].finish_reason, expected)
                chunk = handle_cohere_stream_chunk({"apiFormat": "COHERE", "text": "BILLING",
                                                    "finishReason": reason})
                self.assertEqual(chunk.choices[0].finish_reason, expected)

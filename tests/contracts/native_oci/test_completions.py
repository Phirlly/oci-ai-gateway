"""Native response compatibility, with explicit desired safety assertions."""

import unittest

from demo.results import completion
from runtime.gateway_http import GatewayError
from payload_fixture import MODEL, ROUTE, USAGE, framed_completion, transformed_completion


class CompletionControls(unittest.TestCase):
    def test_complete_response_preserves_model_text_and_provider_usage(self):
        result = transformed_completion()
        self.assertEqual(result.model, MODEL)
        self.assertEqual(completion(framed_completion(result), ROUTE), ("BILLING", USAGE))

    def test_token_limited_response_is_rejected(self):
        result = transformed_completion("MAX_TOKENS")
        with self.assertRaises(GatewayError):
            completion(framed_completion(result), ROUTE)

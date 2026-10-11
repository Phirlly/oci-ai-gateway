"""Native stream boundary/usage controls and desired failure handling."""

import unittest

from demo.results import streamed_completion
from runtime.gateway_http import GatewayError
from payload_fixture import MODEL, ROUTE, event, framed_stream, transformed_stream


class StreamControls(unittest.TestCase):
    def test_fragmented_complete_stream_preserves_content_and_model(self):
        wire = event("BILL") + event("ING") + event(finish="COMPLETE") + "data: [DONE]\n\n"
        chunks = transformed_stream([wire[:12], wire[12:93], wire[93:]])
        self.assertEqual({chunk.model for chunk in chunks}, {MODEL})
        self.assertEqual(streamed_completion(framed_stream(chunks), ROUTE)[0], "BILLING")
        self.assertEqual([c.choices[0].finish_reason for c in chunks if c.choices[0].finish_reason], ["stop"])

    def test_token_limited_stream_is_rejected(self):
        chunks = transformed_stream([event("BILLING"), event(finish="MAX_TOKENS")])
        with self.assertRaises(GatewayError):
            streamed_completion(framed_stream(chunks), ROUTE)

    def test_provider_usage_is_unknown_at_this_adapter_boundary(self):
        chunks = transformed_stream([event("BILLING"), event(finish="COMPLETE", usage=True)])
        self.assertEqual(streamed_completion(framed_stream(chunks), ROUTE), ("BILLING", None))

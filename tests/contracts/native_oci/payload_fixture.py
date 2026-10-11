"""Synthetic native payloads and gateway framing; no proxy/network claim."""

import json
from unittest.mock import MagicMock

import httpx
from litellm import ModelResponse
from litellm.llms.oci.chat.transformation import OCIChatConfig, OCIStreamWrapper, _iter_sse_events

from runtime.gateway_http import Response

MODEL = "google.gemini-2.5-flash-lite"
COMPARTMENT = "ocid1.compartment.oc1..synthetic"
ROUTE = "oci-managed"
USAGE = {"prompt_tokens": 17, "completion_tokens": 3, "total_tokens": 20}


def response_body(finish="COMPLETE"):
    return {
        "modelId": MODEL, "modelVersion": "synthetic",
        "chatResponse": {
            "apiFormat": "GENERIC", "timeCreated": "2026-10-10T00:00:00Z",
            "choices": [{"index": 0, "finishReason": finish, "message": {
                "role": "ASSISTANT", "content": [{"type": "TEXT", "text": "BILLING"}],
            }}],
            "usage": {"promptTokens": 17, "completionTokens": 3, "totalTokens": 20},
        },
    }


def transformed_completion(finish="COMPLETE"):
    return OCIChatConfig().transform_response(
        model=MODEL, raw_response=httpx.Response(200, json=response_body(finish)),
        model_response=ModelResponse(), logging_obj=MagicMock(), request_data={},
        messages=[], optional_params={}, litellm_params={}, encoding=None,
    )


def framed_completion(value):
    return Response(200, value.model_dump_json().encode(), {"x-litellm-model-id": ROUTE})


def event(text=None, finish=None, usage=False):
    value = {"index": 0}
    if text is not None:
        value["message"] = {"role": "ASSISTANT", "content": [{"type": "TEXT", "text": text}]}
    if finish is not None:
        value["finishReason"] = finish
    if usage:
        value["usage"] = {"promptTokens": 17, "completionTokens": 3, "totalTokens": 20}
    return "data: " + json.dumps(value) + "\n\n"


def transformed_stream(fragments):
    logging_obj = MagicMock()
    logging_obj.model_call_details = {"custom_llm_provider": "oci", "litellm_params": {}}
    # Exhaust the actual iterator; chunk_creator alone misses EOF finalization.
    return list(OCIStreamWrapper(
        completion_stream=_iter_sse_events(iter(fragments)), model=MODEL,
        custom_llm_provider="oci", logging_obj=logging_obj,
    ))


def framed_stream(chunks):
    # Synthetic downstream framing mirrors a fully exhausted proxy iterator.
    wire = "".join("data: " + chunk.model_dump_json() + "\n\n" for chunk in chunks)
    return Response(200, (wire + "data: [DONE]\n\n").encode(), {"x-litellm-model-id": ROUTE})

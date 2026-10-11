"""Synthetic OpenAI Chat Completions and final empty-choice usage chunks."""

import json

MODEL = "gpt-4.1-mini-2025-04-14"
USAGE = {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}


def response(stream):
    common = {"id": "chatcmpl-synthetic", "created": 1, "model": MODEL}
    if not stream:
        return {**common, "object": "chat.completion", "usage": USAGE,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "BILLING"}, "finish_reason": "stop"}]}
    chunks = [
        {"choices": [{"index": 0, "delta": {"content": "BILLING"}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        {"choices": [], "usage": USAGE},
    ]
    return [("data: " + json.dumps({**common, "object": "chat.completion.chunk", **chunk}) + "\n\n").encode()
            for chunk in chunks] + [b"data: [DONE]\n\n"]

"""Synthetic Anthropic wire payloads consumed by the actual pinned adapter."""


def external_response(streaming):
    message = {"id": "msg_synthetic", "type": "message", "role": "assistant",
               "model": "claude-sonnet-4-6", "content": [{"type": "text", "text": "BILLING"}],
               "stop_reason": "end_turn", "stop_sequence": None,
               "usage": {"input_tokens": 17, "output_tokens": 3}}
    if not streaming:
        return message
    return [
        {"type": "message_start", "message": {**message, "content": [], "stop_reason": None,
                                               "usage": {"input_tokens": 17, "output_tokens": 0}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "BILLING"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
         "usage": {"output_tokens": 3}},
        {"type": "message_stop"},
    ]

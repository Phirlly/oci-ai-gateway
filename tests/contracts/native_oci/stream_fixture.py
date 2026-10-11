"""Synthetic native iterators with observable cleanup and failure notification."""

import threading
from unittest.mock import AsyncMock, MagicMock

from litellm.llms.oci.chat.transformation import OCIStreamWrapper
from payload_fixture import MODEL, event


class SyncEvents:
    def __init__(self, events):
        self.events = iter(events)
        self.closed = 0

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.events)

    def close(self):
        self.closed += 1


class AsyncEvents(SyncEvents):
    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.events)
        except StopIteration:
            raise StopAsyncIteration from None

    async def aclose(self):
        self.closed += 1


def wrapper(events, *, asynchronous=False):
    source = (AsyncEvents if asynchronous else SyncEvents)(events)
    log = MagicMock()
    log.model_call_details = {"custom_llm_provider": "oci", "litellm_params": {}}
    log._llm_caching_handler = None
    log._on_deferred_stream_complete = None
    log.async_success_handler = AsyncMock()
    log.dispatch_success_handlers = AsyncMock()
    log.dispatch_failure_handlers = AsyncMock()
    failure_notified = threading.Event()
    log.failure_handler.side_effect = lambda *args: failure_notified.set()
    result = OCIStreamWrapper(source, MODEL, log, custom_llm_provider="oci")
    return result, source, log, failure_notified


def text_then_finish(reason):
    return [event("BILLING").strip(), event(finish=reason).strip()]

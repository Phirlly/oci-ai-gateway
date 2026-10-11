"""Observe emitted proxy logs without replacing built-in redaction handlers."""

import io
import logging
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from unittest.mock import patch

from socket_signer_fixture import PRIVATE_MARKER, SIGNATURE_MARKER, SocketProxyCase


class SocketProxyLogging(SocketProxyCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.capture = io.StringIO()
        stack = self.enterContext(ExitStack())
        stack.enter_context(redirect_stdout(self.capture))
        stack.enter_context(redirect_stderr(self.capture))
        handlers = set()
        for name, logger in logging.Logger.manager.loggerDict.items():
            if not isinstance(logger, logging.Logger) or not name.startswith("LiteLLM"):
                continue
            previous = logger.level
            logger.setLevel(logging.INFO)
            stack.callback(logger.setLevel, previous)
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler) and handler not in handlers:
                    handlers.add(handler)
                    stack.enter_context(patch.object(handler, "stream", self.capture))
        self.assertTrue(handlers, "no real LiteLLM log handlers captured")

    async def test_success_stream_and_provider_error_do_not_emit_signature(self):
        for streaming, mode, expected in ((False, "complete", 200), (True, "complete", 200),
                                           (False, "rate_limit", 429)):
            with self.subTest(streaming=streaming, mode=mode):
                self.probe.upstream.mode = mode
                response = await self.request({"stream": streaming})
                self.assertEqual(response.status_code, expected, response.text[:200])
                self.assertIn(SIGNATURE_MARKER, self.probe.upstream.requests[-1].headers["authorization"])
                self.assertNotIn(SIGNATURE_MARKER, self.capture.getvalue())
        self.assertIn("429", self.capture.getvalue())

    async def test_signer_failure_stays_sanitized_and_never_sends_inference(self):
        for mode in ("malformed", "unavailable"):
            with self.subTest(mode=mode):
                self.socket.mode = mode
                response = await self.request()
                self.assertNotEqual(response.status_code, 200)
                self.assertIn("Native signing unavailable", response.text)
                self.assertNotIn(PRIVATE_MARKER, response.text + self.capture.getvalue())
                self.assertEqual(self.probe.upstream.requests, [])
        self.assertIn("Native signing unavailable", self.capture.getvalue())

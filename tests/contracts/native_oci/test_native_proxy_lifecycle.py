"""Probe initialization must not retain callbacks from previous routers."""

import unittest
import os

import litellm
from runtime import oci_gateway_config

from native_proxy_fixture import NativeProxyCase


class NativeProxyLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_completed_probe_restores_original_callback_lists(self):
        names = ("callbacks", "input_callback", "_async_input_callback", "success_callback",
                 "failure_callback", "_async_success_callback", "_async_failure_callback")
        originals = {name: getattr(litellm, name) for name in names}
        contents = {name: tuple(value) for name, value in originals.items()}
        original_path = oci_gateway_config.GATEWAY_CONFIG
        original_key = os.environ.get("ANTHROPIC_API_KEY")
        probe = NativeProxyCase()
        try:
            await probe.asyncSetUp()
        finally:
            await probe.close_probe()
        for name, original in originals.items():
            with self.subTest(callback_list=name):
                self.assertIs(getattr(litellm, name), original)
                self.assertEqual(tuple(original), contents[name])
        self.assertEqual(oci_gateway_config.GATEWAY_CONFIG, original_path)
        self.assertEqual(os.environ.get("ANTHROPIC_API_KEY"), original_key)

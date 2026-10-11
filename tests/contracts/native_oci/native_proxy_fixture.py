"""Actual proxy config/auth/router fixture with owned offline clients."""

import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import httpx
import litellm
from litellm.proxy import proxy_server

from payload_fixture import COMPARTMENT, MODEL, ROUTE
from runtime.gateway_http import Response

MASTER = "sk-synthetic-native-probe-only"


class NativeProxyCase(unittest.IsolatedAsyncioTestCase):
    allow_client_credentials = False

    async def asyncSetUp(self):
        self.saved_callbacks = {name: getattr(litellm, name) for name in (
            "callbacks", "input_callback", "_async_input_callback", "success_callback", "failure_callback",
            "_async_success_callback", "_async_failure_callback",
        )}
        self.saved_drop = litellm.drop_params
        self.saved_proxy = {name: getattr(proxy_server, name) for name in (
            "llm_router", "llm_model_list", "general_settings", "master_key",
        )}
        self.client = self.probe = None
        self.directory = tempfile.TemporaryDirectory(prefix="native-proxy-")
        self.addAsyncCleanup(self.close_probe)
        for name in self.saved_callbacks:
            setattr(litellm, name, [])
        litellm.drop_params = False
        proxy_server.llm_router = None
        proxy_server.user_api_key_cache.flush_cache()
        path = Path(self.directory.name)
        shutil.copyfile(Path(__file__).with_name("native_proxy_callback.py"),
                        path / "native_proxy_callback.py")
        config = {
            "model_list": [{
                "model_name": ROUTE, "model_info": {"id": ROUTE},
                "litellm_params": {"model": "oci/" + MODEL, "oci_region": "us-ashburn-1",
                                  "oci_compartment_id": COMPARTMENT,
                                  "additional_drop_params": ["stream_options"],
                                  "max_tokens": 32, "num_retries": 0},
            }],
            "litellm_settings": {"callbacks": ["native_proxy_callback.INSTANCE"],
                                 "drop_params": False, "num_retries": 0},
            "router_settings": {"num_retries": 0, "allowed_fails": 1000},
            "general_settings": {"master_key": MASTER,
                                 "allow_client_side_credentials": self.allow_client_credentials},
        }
        config_path = path / "config.yaml"
        config_path.write_text(json.dumps(config))
        await proxy_server.initialize(config=str(config_path), drop_params=False, request_timeout=3)
        matches = [item for item in litellm.callbacks if type(item).__name__ == "NativeProbe"]
        self.assertEqual(len(matches), 1, "config did not load exactly one module instance")
        self.probe = matches[0]
        self.assertIs(litellm.drop_params, False)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy_server.app),
                                       base_url="http://proxy.test", timeout=5)

    async def close_probe(self):
        if self.client is not None:
            await self.client.aclose()
        if self.probe is not None:
            await self.probe.upstream.close()
        if proxy_server.llm_router is not None:
            proxy_server.llm_router.reset()
        for name, value in self.saved_callbacks.items():
            setattr(litellm, name, value)
        for name, value in self.saved_proxy.items():
            setattr(proxy_server, name, value)
        litellm.drop_params = self.saved_drop
        self.directory.cleanup()

    async def request(self, extra=None, *, key=MASTER):
        body = {"model": ROUTE, "messages": [{"role": "user", "content": "Synthetic request"}],
                "max_tokens": 32}
        body.update(extra or {})
        headers = {"authorization": "Bearer " + key} if key is not None else {}
        async with asyncio.timeout(5):
            return await self.client.post("/chat/completions", json=body, headers=headers)

    def result(self, response):
        return Response(response.status_code, response.content, dict(response.headers))

"""Actual proxy config/auth/router fixture with owned offline clients."""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import httpx
import litellm
from litellm.proxy import proxy_server
from litellm.integrations.custom_logger import CustomLogger

from payload_fixture import COMPARTMENT, MODEL, ROUTE
from runtime.gateway_http import Response
from runtime import oci_gateway_config
from runtime.oci_signing_client import SocketSigner
from native_proxy_upstream import NativeUpstream

MASTER = "sk-synthetic-native-probe-only"
EXTERNAL = "external-anthropic"


class OfflineTransport(CustomLogger):
    """Replace only outbound HTTP after the production policy has run."""

    def __init__(self, upstream):
        super().__init__()
        self.upstream = upstream

    async def async_pre_call_deployment_hook(self, kwargs, call_type):
        kwargs["client"] = (self.upstream.openai(kwargs["api_key"]) if kwargs.get("custom_llm_provider") == "openai"
                            or str(kwargs.get("model", "")).startswith("openai/") else self.upstream.handler)
        return kwargs


class NativeProxyCase(unittest.IsolatedAsyncioTestCase):
    allow_client_credentials = False
    providers = ("oci", "anthropic")

    async def asyncSetUp(self):
        self.saved_callbacks = {name: getattr(litellm, name) for name in (
            "callbacks", "input_callback", "_async_input_callback", "success_callback", "failure_callback",
            "_async_success_callback", "_async_failure_callback",
        )}
        self.saved_drop = litellm.drop_params
        self.saved_proxy = {name: getattr(proxy_server, name) for name in (
            "llm_router", "llm_model_list", "general_settings", "master_key",
        )}
        self.client = self.probe = self.upstream = None
        self.context = ExitStack()
        self.directory = tempfile.TemporaryDirectory(prefix="native-proxy-")
        self.addAsyncCleanup(self.close_probe)
        for name in self.saved_callbacks:
            setattr(litellm, name, [])
        litellm.drop_params = False
        proxy_server.llm_router = None
        proxy_server.user_api_key_cache.flush_cache()
        path = Path(self.directory.name)
        (path / "runtime").mkdir()
        shutil.copyfile(Path(oci_gateway_config.__file__).with_name("oci_gateway_loader.py"),
                        path / "runtime" / "oci_gateway_loader.py")
        config = {
            "model_list": [{
                "model_name": ROUTE, "model_info": {"id": ROUTE},
                "litellm_params": {"model": "oci/" + MODEL, "oci_region": "us-ashburn-1",
                                  "oci_compartment_id": COMPARTMENT,
                                  "additional_drop_params": ["stream_options"],
                                  "max_tokens": 32, "num_retries": 0},
            }, {"model_name": EXTERNAL, "model_info": {"id": EXTERNAL},
                "litellm_params": {"model": "anthropic/claude-sonnet-4-6",
                                   "api_key": "os.environ/ANTHROPIC_API_KEY"}}],
            "litellm_settings": {"callbacks": ["runtime.oci_gateway_loader.INSTANCE"],
                                 "drop_params": False, "num_retries": 0},
            "router_settings": {"num_retries": 0, "allowed_fails": 1000},
            "general_settings": {"master_key": MASTER,
                                 "allow_client_side_credentials": self.allow_client_credentials},
        }
        config_path = path / "config.yaml"
        if self.providers != ("oci", "anthropic"):
            from runtime.provider_selection import model_routes
            examples = {"oci": MODEL, "anthropic": "claude-sonnet-4-6", "openai": "gpt-4.1-mini-2025-04-14"}
            config["model_list"] = model_routes({"models": {p: examples[p] for p in self.providers},
                                                 "inference_region": "us-ashburn-1", "compartment_ocid": COMPARTMENT})
        config_path.write_text(json.dumps(config))
        config_path.chmod(0o600)
        self.context.enter_context(patch.object(oci_gateway_config, "GATEWAY_CONFIG", config_path))
        self.context.enter_context(patch.dict(os.environ, {"ANTHROPIC_API_KEY": "synthetic-external-key",
                                                         "OPENAI_API_KEY": "synthetic-openai-key"}))
        await proxy_server.initialize(config=str(config_path), drop_params=False, request_timeout=3)
        matches = [item for item in litellm.callbacks if type(item).__name__ == "NativeGateway"]
        self.assertEqual(len(matches), 1, "config did not load exactly one module instance")
        self.probe = matches[0]
        if "oci" in self.providers:
            self.assertIsInstance(self.probe.oci_signer, SocketSigner)
        else:
            self.assertIsNone(self.probe.oci_signer)
        self.upstream = NativeUpstream()
        litellm.callbacks.append(OfflineTransport(self.upstream))
        self.assertIs(litellm.drop_params, False)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy_server.app),
                                       base_url="http://proxy.test", timeout=5)

    async def close_probe(self):
        if self.client is not None:
            await self.client.aclose()
        if self.upstream is not None:
            await self.upstream.close()
        if proxy_server.llm_router is not None:
            proxy_server.llm_router.reset()
        for name, value in self.saved_callbacks.items():
            setattr(litellm, name, value)
        for name, value in self.saved_proxy.items():
            setattr(proxy_server, name, value)
        litellm.drop_params = self.saved_drop
        self.directory.cleanup()
        self.context.close()

    async def request(self, extra=None, *, key=MASTER, headers=None):
        body = {"model": ROUTE, "messages": [{"role": "user", "content": "Synthetic request"}],
                "max_tokens": 32}
        body.update(extra or {})
        request_headers = {"authorization": "Bearer " + key} if key is not None else {}
        request_headers.update(headers or {})
        async with asyncio.timeout(5):
            return await self.client.post("/chat/completions", json=body, headers=request_headers)

    def result(self, response):
        return Response(response.status_code, response.content, dict(response.headers))

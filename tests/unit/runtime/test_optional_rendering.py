"""Enabled providers alone reach the rendered gateway and secret environment."""

import json
import tempfile
import unittest
from pathlib import Path

from runtime.gateway_entrypoint import entry_environment
from runtime.presenter import Presenter
from runtime.provider_selection import model_aliases
from runtime.runtime_bundle import RuntimeBundle
from runtime.runtime_files import runtime_files
from .optional_fixture import SUBSETS, credentials, settings


class OptionalRenderingTests(unittest.TestCase):
    def test_all_subsets_render_correct_adapters_and_only_selected_secrets(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers), tempfile.TemporaryDirectory() as directory:
                value = settings(providers)
                presenter = Presenter(value["deployment_id"], value["presenter_email"], model_aliases(value))
                files = runtime_files(RuntimeBundle(value, "8.8.4.4", credentials(providers), presenter))
                config = json.loads(files["gateway.json"])
                rows = config["model_list"]
                self.assertEqual(tuple(row["model_name"] for row in rows), presenter.models)
                self.assertEqual({row["litellm_params"]["model"].split("/")[0] for row in rows}, set(providers))
                self.assertIn("runtime.oci_gateway_loader.INSTANCE", config["litellm_settings"]["callbacks"])
                path = Path(directory) / "secrets.json"
                path.write_text(files["gateway-secrets.json"])
                path.chmod(0o600)
                environment = entry_environment(path)
                self.assertEqual(set(environment) & {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OCI_GENAI_API_KEY"},
                                 {p.upper() + "_API_KEY" for p in providers if p != "oci"})
                self.assertNotIn("demo_password", files["gateway-secrets.json"])

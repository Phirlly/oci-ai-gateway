"""Render the packaged cloud-init and install its emitted assets outside the repo."""

import base64
import gzip
import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from deployment.console_package import ConsolePackage
from runtime.install_assets import install_assets

ROOT = Path(__file__).resolve().parents[3]


class ConsoleBootstrapContracts(unittest.TestCase):
    def test_emitted_assets_install_exact_packaged_bytes(self):
        package = ConsolePackage.build(ROOT, repository="synthetic/gateway", commit="a" * 40)
        with tempfile.TemporaryDirectory(prefix="gateway-console-bootstrap-") as directory:
            extracted = Path(directory) / "package"
            with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
                archive.extractall(extracted)
            # Render the production template with no provider, state or credentials.
            render = extracted / "render"
            render.mkdir()
            for name in ("bootstrap.tf", "source.json"):
                (render / name).write_bytes((extracted / name).read_bytes())
            (render / "settings.tf.json").write_text(json.dumps({"locals": {
                "runtime_settings": {"schema_version": 4},
                "console_settings": {"schema_version": 2},
            }}))
            binary = os.environ.get("GATEWAY_TERRAFORM_15", str(ROOT / ".cache/terraform/1.5.7/terraform"))
            result = subprocess.run([binary, "-chdir=" + str(render), "console", "-no-color"],
                                    input="jsonencode(yamldecode(local.cloud_init))\n",
                                    capture_output=True, text=True, timeout=30,
                                    env={**os.environ, "TF_IN_AUTOMATION": "1", "TF_INPUT": "0"})
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads(json.loads(result.stdout))
            files = {item["path"]: item for item in config["write_files"]}
            for item in files.values():
                self.assertEqual((item["owner"], item["permissions"]), ("root:root", "0600"))
            assets = self.content(files["/opt/oci-ai-gateway/assets.json"])
            installer = self.content(files["/opt/oci-ai-gateway/install_assets.py"])
            self.assertEqual(installer, (extracted / "runtime/install_assets.py").read_bytes())
            self.assertEqual(self.content(files["/etc/oci-ai-gateway-source.json"]),
                             (extracted / "source.json").read_bytes())
            installed = Path(directory) / "installed"
            installed.mkdir()
            install_assets(assets, installed)
            install_assets(assets, installed)  # Repeated installation must preserve immutable bytes.
            services = {
                "runtime/systemd/oci-ai-gateway-console-bootstrap.service": "oci-ai-gateway-bootstrap.service",
                "runtime/systemd/oci-ai-gateway-bootstrap.timer": "oci-ai-gateway-bootstrap.timer",
            }
            for name in json.loads(assets):
                destination = (installed / "etc/systemd/system" / services[name] if name in services
                               else installed / "opt/oci-ai-gateway" / name)
                self.assertEqual(destination.read_bytes(), (extracted / name).read_bytes(), name)

    @staticmethod
    def content(item):
        if item.get("encoding") == "gz+b64":
            return gzip.decompress(base64.b64decode(item["content"], validate=True))
        if "encoding" in item:
            raise AssertionError("Unexpected cloud-init encoding")
        return item["content"].encode()

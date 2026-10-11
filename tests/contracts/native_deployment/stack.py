"""Run production services with synthetic secrets, isolated networking and ports."""

import json
import os
from types import SimpleNamespace

from runtime.oci_adapter_overlay import prepare_overlay
from runtime.runtime_files import runtime_files
from tests.contracts.native_oci.container import prepare_engine, run_container
from tests.contracts.runtime.stack import GatewayStack, ROOT, docker_command, run_command


class NativeStack(GatewayStack):
    def prepare_inputs(self):
        super().prepare_inputs()
        secrets_file = self.directory / "gateway-secrets.json"
        credentials = json.loads(secrets_file.read_text())
        del credentials["oci_api_key"]
        bundle = SimpleNamespace(settings={
            "schema_version": 3, "model_id": "google.gemini-2.5-flash-lite",
            "inference_region": "us-ashburn-1", "compartment_ocid": "ocid1.compartment.oc1..synthetic",
            "external_model_id": "claude-sonnet-4-6"}, credentials=credentials, public_ip="8.8.4.4")
        for name, body in runtime_files(bundle).items():
            path = self.directory / name
            path.write_text(body)
            path.chmod(0o600)
        signing = self.directory / "signing"
        signing.mkdir(mode=0o700)
        self.set_environment({"GATEWAY_STATE_DIR": str(self.directory), "GATEWAY_SOURCE_DIR": str(ROOT),
                              "GATEWAY_SIGNING_DIR": str(signing)})
        return self

    def start(self):
        prepare_engine()
        exported = run_container(["-m", "runtime.oci_adapter_overlay"])
        if exported.returncode:
            raise RuntimeError("Pinned native source export failed")
        overlay = prepare_overlay(json.loads(exported.stdout))
        for module in ("generic", "transformation"):
            path = self.directory / ("oci-" + module + ".py")
            path.write_text(overlay["llms/oci/chat/" + module + ".py"])
            path.chmod(0o600)
        config = json.loads(run_command(docker_command() + ["compose", "-f",
                            str(ROOT / "runtime/compose.native.yaml"), "config", "--format", "json"]))
        # Only test isolation changes: no public edge, outbound network or published ports.
        del config["services"]["edge"]
        config["networks"]["frontend"]["internal"] = True
        for name, network in config["networks"].items():
            network["name"] = self.project + "_" + name
        for name, volume in config["volumes"].items():
            volume["name"] = self.project + "_" + name
        config["services"]["gateway"].pop("ports")
        config["services"]["gateway"]["volumes"].append({
            "type": "bind", "source": str(ROOT / "tests"), "target": "/checks/tests", "read_only": True})
        self.manifest = self.directory / "compose.json"
        self.manifest.write_text(json.dumps(config))
        self.manifest.chmod(0o600)
        command = self.command()
        run_command(command + ["config", "--quiet"])
        self.started = True
        run_command(command + ["pull", "--quiet"], timeout=1200)
        run_command(command + ["up", "-d", "--wait", "--wait-timeout", "180"], timeout=240)
        for network in ("database", "frontend"):
            internal = run_command(docker_command() + ["network", "inspect", self.project + "_" + network,
                                   "--format", "{{.Internal}}"]).strip()
            if internal != "true":
                raise RuntimeError("Native contract network permits outbound traffic")

    def check_startup(self):
        return run_command(self.command() + ["exec", "-T", "-e", "PYTHONPATH=/app:/checks",
            "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "GATEWAY_TEST_URL=http://127.0.0.1:4000",
            "-e", "GATEWAY_TEST_MASTER_KEY=" + os.environ["GATEWAY_TEST_MASTER_KEY"], "gateway",
            "python3", "-m", "unittest", "tests.contracts.native_deployment.test_startup", "-v"], timeout=45)

    def command(self):
        return docker_command() + ["compose", "--project-name", self.project, "-f", str(self.manifest)]

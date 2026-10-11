"""Start the actual external-only Console services with isolated synthetic inputs."""

import os
import sys
from types import SimpleNamespace

from runtime.runtime_files import runtime_files
from tests.contracts.native_deployment.stack import NativeStack
from tests.contracts.runtime.stack import GatewayStack, ROOT
from tests.unit.runtime.optional_fixture import credentials, settings


class ExternalStack(NativeStack):
    compose_files = ("compose.cloud.yaml", "compose.console.yaml")
    startup_test = "tests.contracts.optional_deployment.test_startup"

    def prepare_inputs(self):
        if sys.platform == "linux" and os.geteuid() != 0:
            raise RuntimeError("External-only Compose contract requires root on Linux for private config ownership")
        GatewayStack.prepare_inputs(self)
        bundle = SimpleNamespace(settings=settings(("openai",)), credentials=credentials(("openai",)),
                                 public_ip="8.8.4.4")
        for name, content in runtime_files(bundle).items():
            path = self.directory / name
            path.write_text(content)
            path.chmod(0o600)
        status = self.directory / "status"
        status.mkdir(mode=0o755)
        self.set_environment({"GATEWAY_STATE_DIR": str(self.directory), "GATEWAY_SOURCE_DIR": str(ROOT),
                              "GATEWAY_STATUS_DIR": str(status),
                              "GATEWAY_TEST_MASTER_KEY": bundle.credentials["gateway_master_key"]})
        return self

    def prepare_adapter(self):
        # Production external-only preparation does not need the native overlay.
        pass

    def check_manifest(self, config):
        mounts = config["services"]["gateway"]["volumes"]
        if any("signing" in row["target"] or row["target"].endswith(("generic.py", "transformation.py"))
               for row in mounts):
            raise RuntimeError("External-only gateway unexpectedly mounts native signing assets")
        if not any(row["target"] == "/srv/gateway-status" for row in config["services"]["edge"]["volumes"]):
            raise RuntimeError("Console status mount is missing")

"""Prove atomic key publication needs and receives a new container bind mount."""

import json

from runtime.console_credentials import internal_credentials, publish_credentials
from tests.contracts.native_deployment.stack import NativeStack
from tests.contracts.runtime.stack import run_command


class CredentialActivation(NativeStack):
    def prepare_inputs(self):
        super().prepare_inputs()
        values = internal_credentials(self.directory)
        values["external_api_key"] = "synthetic-before-refresh"
        # Replace only the synthetic fixture before starting any container.
        (self.directory / "gateway-secrets.json").write_text(json.dumps(values))
        (self.directory / "database-password").write_text(values["database_password"])
        self.set_environment({"GATEWAY_TEST_MASTER_KEY": values["gateway_master_key"]})
        return self

    def mounted_key(self):
        return run_command(self.command() + ["exec", "-T", "gateway", "python3", "-c",
                           "import json; print(json.load(open('/run/secrets/gateway.json'))['external_api_key'])"]).strip()

    def check_refresh(self):
        original = (self.directory / "console-credentials.json").read_bytes()
        database = run_command(self.command() + ["ps", "--quiet", "database"]).strip()
        gateway = run_command(self.command() + ["ps", "--quiet", "gateway"]).strip()
        publish_credentials(self.directory, {**internal_credentials(self.directory), "external_api_key": "synthetic-after-refresh"})
        if self.mounted_key() != "synthetic-before-refresh":
            raise RuntimeError("Expected the existing container to retain the old bind-mounted file")
        run_command(self.command() + ["up", "-d", "--no-deps", "--force-recreate", "--wait",
                                      "--wait-timeout", "180", "gateway"], timeout=240)
        if self.mounted_key() != "synthetic-after-refresh":
            raise RuntimeError("Recreated gateway did not observe the corrected provider key")
        if run_command(self.command() + ["ps", "--quiet", "gateway"]).strip() == gateway:
            raise RuntimeError("Gateway container was not recreated")
        if (run_command(self.command() + ["ps", "--quiet", "database"]).strip() != database
                or (self.directory / "console-credentials.json").read_bytes() != original):
            raise RuntimeError("Key refresh changed the database or internal credentials")

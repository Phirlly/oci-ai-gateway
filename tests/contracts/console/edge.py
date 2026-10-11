"""Serve the real status route while gateway/database containers do not exist."""

import json
import re
import time
from urllib.request import urlopen

from runtime.console_status import publish_status
from runtime.runtime_files import caddy_config
from tests.contracts.runtime.stack import GatewayStack, ROOT, docker_command, run_command


class StatusEdge(GatewayStack):
    def prepare_inputs(self):
        super().prepare_inputs()
        self.status = self.directory / "public"
        publish_status(self.status, "WAITING_CREDENTIALS", {"run": 1, "passed": 0, "finished_at": ""})
        config = caddy_config("8.8.4.4", console=True)
        # Test isolation only: loopback HTTP without public ACME/certificate issuance.
        config, count = re.subn(r"  tls \{\n    issuer acme \{.*?\n    \}\n  \}\n", "", config, flags=re.S)
        if count != 1:
            raise RuntimeError("Expected exactly one production TLS block")
        (self.directory / "Caddyfile").write_text(config.replace("https://8.8.4.4", ":8080"))
        self.set_environment({"GATEWAY_STATE_DIR": str(self.directory), "GATEWAY_SOURCE_DIR": str(ROOT),
                              "GATEWAY_STATUS_DIR": str(self.status)})
        config = json.loads(run_command(docker_command() + ["compose", "-f", str(ROOT / "runtime/compose.native.yaml"),
                            "-f", str(ROOT / "runtime/compose.console.yaml"), "config", "--format", "json"]))
        config["services"]["edge"]["ports"] = [{"host_ip": "127.0.0.1", "target": 8080, "published": "0", "protocol": "tcp"}]
        for name, network in config["networks"].items():
            network.update(name=self.project + "_" + name, internal=True)
        for name, volume in config["volumes"].items():
            volume["name"] = self.project + "_" + name
        mounts = config["services"]["edge"]["volumes"]
        if not any(row.get("source") == str(self.status) and row["target"] == "/srv/gateway-status" for row in mounts):
            raise RuntimeError("Console status mount is missing")
        if any(row.get("source") == str(self.directory) for row in mounts):
            raise RuntimeError("Private state directory must not be mounted on edge")
        self.manifest = self.directory / "compose.json"
        self.manifest.write_text(json.dumps(config))
        return self

    def command(self):
        return docker_command() + ["compose", "--project-name", self.project, "-f", str(self.manifest)]

    def check(self):
        self.started = True
        run_command(self.command() + ["pull", "--quiet", "edge"], timeout=600)
        run_command(self.command() + ["up", "-d", "--no-deps", "edge"], timeout=60)
        if len(run_command(self.command() + ["ps", "--quiet"]).strip().splitlines()) != 1:
            raise RuntimeError("Status startup unexpectedly started another service")
        address = run_command(self.command() + ["port", "edge", "8080"]).strip()
        if not address.startswith("127.0.0.1:"):
            raise RuntimeError("Status contract must use loopback only")
        url = "http://" + address + "/deployment-status"
        deadline = time.monotonic() + 15
        while True:
            try:
                with urlopen(url, timeout=2) as response:
                    value = json.load(response)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Independent status endpoint did not start") from None
                time.sleep(0.25)
        if value["status"] != "WAITING_CREDENTIALS":
            raise RuntimeError("Status did not expose the waiting state")
        publish_status(self.status, "READY", {"run": 1, "passed": 8, "finished_at": "2026-10-11T12:00:00Z"})
        with urlopen(url, timeout=2) as response:
            if json.load(response)["status"] != "READY":
                raise RuntimeError("Atomic status update is invisible to the mounted directory")

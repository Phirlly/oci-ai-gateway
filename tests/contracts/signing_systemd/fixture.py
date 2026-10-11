"""Own unique transient units and one network-disabled container on Ubuntu CI."""

import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from runtime.oci_adapter_overlay import IMAGE
from tests.contracts.native_oci.container import prepare_engine
from tests.contracts.runtime.stack import ROOT, docker_command, run_command


class SystemdSocket:
    def __init__(self):
        self.name = "gateway-systemd-contract-" + secrets.token_hex(8)
        self.socket_dir = "/run/" + self.name
        self.units, self.directory, self.container = [], None, False

    def control(self, *arguments):
        return run_command(["sudo", "-n", "systemctl", *arguments], timeout=30).strip()

    def __enter__(self):
        try:
            if not Path("/run/systemd/system").is_dir():
                raise RuntimeError("This Linux contract requires a running systemd manager")
            for value in (str(ROOT), sys.executable):
                if re.fullmatch(r"[/A-Za-z0-9_.-]+", value) is None:
                    raise RuntimeError("Contract unit paths must not need systemd escaping")
            prepare_engine()
            self.directory = Path(tempfile.mkdtemp(prefix=self.name + "-", dir="/tmp"))
            for suffix in ("socket", "service"):
                body = (ROOT / "runtime/systemd" / ("oci-ai-gateway-signing." + suffix)).read_text()
                body = body.replace("oci-ai-gateway-signing", self.name)
                body = body.replace("/opt/oci-ai-gateway/oci-cli/bin/python -m runtime.oci_signing_entrypoint",
                                    sys.executable + " -m tests.contracts.signing_systemd.worker " + self.socket_dir + "/sign.sock")
                body = body.replace("/opt/oci-ai-gateway", str(ROOT))
                if suffix == "service":
                    body += "Environment=PYTHONDONTWRITEBYTECODE=1\n"
                source = self.directory / (self.name + "." + suffix)
                source.write_text(body)
                target = "/run/systemd/system/" + source.name
                self.units.append(target)
                run_command(["sudo", "-n", "install", "-m", "0644", str(source), target])
            self.control("daemon-reload")
            self.control("start", self.name + ".socket")
            self.container = True  # Cleanup also covers an uncertain Docker reply.
            run_command(docker_command() + ["run", "-d", "--name", self.name, "--pull", "never",
                "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--mount", "type=bind,source=" + str(ROOT / "runtime") + ",target=/checks/runtime,readonly",
                "--mount", "type=bind,source=" + str(ROOT / "tests") + ",target=/checks/tests,readonly",
                "--mount", "type=bind,source=" + self.socket_dir + ",target=/run/contract-signing,readonly",
                "--env", "PYTHONPATH=/checks", "--env", "PYTHONDONTWRITEBYTECODE=1",
                "--entrypoint", "python3", IMAGE, "-c", "import time; time.sleep(300)"])
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def pid(self):
        return self.control("show", "--property=MainPID", "--value", self.name + ".service")

    def probe(self):
        return json.loads(run_command(docker_command() + ["exec", self.name, "python3", "-m",
                                      "tests.contracts.signing_systemd.client"], timeout=20))

    def restart_worker(self):
        self.control("restart", self.name + ".service")

    def restart_container(self):
        run_command(docker_command() + ["restart", "--time", "5", self.name])

    def __exit__(self, *arguments):
        try:
            self.cleanup()
        except BaseException as error:
            raise RuntimeError(f"Cleanup incomplete for {self.name}; units /run/systemd/system/{self.name}.*; "
                               f"socket {self.socket_dir}; retained inputs {self.directory}") from error

    def cleanup(self):
        # Stop on cleanup uncertainty; retain units/paths for exact recovery.
        if self.container:
            run_command(docker_command() + ["rm", "--force", self.name])
            owned = run_command(docker_command() + ["ps", "--all", "--quiet", "--filter", "name=^/" + self.name + "$"])
            if owned.strip():
                raise RuntimeError("Owned signing contract container remains")
        if self.units:
            self.control("stop", self.name + ".socket", self.name + ".service")
            self.control("reset-failed", self.name + ".socket", self.name + ".service")
            run_command(["sudo", "-n", "rm", "--", *self.units])
            self.control("daemon-reload")
            exists = subprocess.run(["sudo", "-n", "test", "-d", self.socket_dir], timeout=10).returncode
            if exists == 0:
                run_command(["sudo", "-n", "rmdir", "--", self.socket_dir])
            elif exists != 1:
                raise RuntimeError("Signing contract directory cleanup could not be verified")
            if any(Path(path).exists() for path in self.units):
                raise RuntimeError("Owned signing contract units remain")
        if self.directory:
            shutil.rmtree(self.directory)

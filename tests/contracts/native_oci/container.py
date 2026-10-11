"""Own each offline pinned-image process and verify exact-name cleanup."""

import secrets
import subprocess
from pathlib import Path

from runtime.oci_adapter_overlay import IMAGE
from tests.contracts.runtime.stack import docker_command, run_command

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def prepare_engine():
    command = docker_command()
    endpoint = run_command(["docker", "context", "inspect", command[-1],
                            "--format", "{{.Endpoints.docker.Host}}"]).strip()
    if not endpoint.startswith("unix://"):
        raise RuntimeError("Native contracts require a local Unix-socket engine")
    run_command(command + ["pull", "--quiet", IMAGE], timeout=1200)


def run_container(arguments, mounts=()):
    name = "gateway-native-contract-" + secrets.token_hex(6)
    docker = docker_command()
    command = docker + [
        "run", "--rm", "--name", name, "--pull=never", "--network=none", "--read-only",
        "--tmpfs", "/tmp", "--entrypoint", "python3", "--workdir", "/checks",
        "-e", "PYTHONPATH=/checks:/work", "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "LITELLM_LOCAL_MODEL_COST_MAP=True", "-v", f"{HERE}:/checks:ro",
        "-v", f"{ROOT / 'runtime'}:/work/runtime:ro", "-v", f"{ROOT / 'demo'}:/work/demo:ro",
    ]
    for source, destination in mounts:
        command.extend(["--mount", f"type=bind,src={source},dst={destination},readonly"])
    try:
        return subprocess.run(command + [IMAGE] + arguments, capture_output=True,
                              text=True, timeout=90)
    finally:
        subprocess.run(docker + ["rm", "--force", name], capture_output=True, timeout=20)
        remains = subprocess.run(docker + ["ps", "--all", "--quiet", "--filter", f"name=^/{name}$"],
                                 check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        if remains:
            raise RuntimeError("Owned native contract container remains: " + name)

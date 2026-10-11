"""Prepare the pinned native overlay and private host socket before Compose."""

import json
import secrets

from .gateway_http import GatewayError
from .host_commands import COMPOSE, SOURCE, _run
from .oci_adapter_overlay import IMAGE, OverlayError, prepare_overlay
from .oci_instance_signer import SDK_VERSION
from .runtime_files import write_private_files

NATIVE_COMPOSE = COMPOSE[:-1] + [SOURCE + "/runtime/compose.native.yaml"]


def ensure_native_dependencies():
    python = SOURCE + "/oci-cli/bin/python"
    if _run([python, "-c", "import oci; print(oci.__version__)"], "OCI SDK verification", 15).stdout.strip() != SDK_VERSION:
        raise GatewayError("Host OCI SDK version does not match native signing requirements")
    try:
        installed = _run(["/usr/bin/git", "--version"], "Git inspection", 15).returncode == 0
    except GatewayError:
        installed = False
    if not installed:
        options = ["/usr/bin/apt-get", "-o", "DPkg::Lock::Timeout=60", "-o", "Acquire::Retries=2"]
        _run(options + ["update"], "Git package index refresh", 180)
        _run(options + ["install", "--yes", "--no-install-recommends", "--no-remove", "git"],
             "Git package installation", 180)
        _run(["/usr/bin/git", "--version"], "Git verification", 15)


def start_native_services(directory, *, compose=NATIVE_COMPOSE):
    ensure_native_dependencies()
    _run(compose + ["pull", "--quiet"], "Pinned container download", 600)
    name = "gateway-native-export-" + secrets.token_hex(8)
    try:
        exported = _run([
            "/usr/bin/docker", "run", "--rm", "--name", name, "--pull", "never",
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--entrypoint", "python3",
            "--env", "PYTHONPATH=/opt/oci-ai-gateway",
            "--mount", "type=bind,source=" + SOURCE + "/runtime,target=/opt/oci-ai-gateway/runtime,readonly",
            IMAGE, "-m", "runtime.oci_adapter_overlay"], "Native source export", 60)
        if len(exported.stdout.encode()) > 256 * 1024:
            raise ValueError
        files = prepare_overlay(json.loads(exported.stdout))
        write_private_files(directory, {"oci-generic.py": files["llms/oci/chat/generic.py"],
                                        "oci-transformation.py": files["llms/oci/chat/transformation.py"]})
    except (ValueError, TypeError, OverlayError):
        raise GatewayError("Native adapter source could not be prepared safely") from None
    finally:
        _run(["/usr/bin/docker", "rm", "--force", name], "Native export cleanup", 30, allow_failure=True)
    _run(["/usr/bin/systemctl", "enable", "--now", "oci-ai-gateway-signing.socket"],
         "Private signing socket activation", 30)
    _run(compose + ["up", "-d", "--wait", "--wait-timeout", "180"], "Native gateway startup", 240)

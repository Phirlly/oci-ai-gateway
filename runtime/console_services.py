"""Console edge startup and explicit process/file-mount refresh after key changes."""

from .host_commands import COMPOSE, SOURCE, _run
from .native_startup import NATIVE_COMPOSE, start_native_services
from .runtime_files import caddy_config, write_private_files

CONSOLE_COMPOSE = NATIVE_COMPOSE + ["-f", SOURCE + "/runtime/compose.console.yaml"]


def _compose(native):
    return CONSOLE_COMPOSE if native else COMPOSE + ["-f", SOURCE + "/runtime/compose.console.yaml"]


def start_edge(directory, public_ip, *, native=True):
    write_private_files(directory, {"Caddyfile": caddy_config(public_ip, console=True)})
    _run(_compose(native) + ["pull", "--quiet", "edge"], "Status edge download", 300)
    _run(_compose(native) + ["up", "-d", "--no-deps", "edge"], "Status edge startup", 60)


def activate_gateway(directory, *, native=True):
    compose = _compose(native)
    if native:
        start_native_services(directory, compose=compose)
    else:
        _run(compose + ["pull", "--quiet"], "Pinned container download", 600)
        _run(compose + ["up", "-d", "--wait", "--wait-timeout", "180"], "Gateway startup", 240)
    # Atomic host file replacement does not change an existing bind-mounted inode.
    _run(compose + ["up", "-d", "--no-deps", "--force-recreate", "--wait",
                            "--wait-timeout", "180", "gateway"], "Provider credential activation", 240)

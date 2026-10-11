"""Console edge startup and explicit process/file-mount refresh after key changes."""

from .host_commands import SOURCE, _run
from .native_startup import NATIVE_COMPOSE, start_native_services
from .runtime_files import caddy_config, write_private_files

CONSOLE_COMPOSE = NATIVE_COMPOSE + ["-f", SOURCE + "/runtime/compose.console.yaml"]


def start_edge(directory, public_ip):
    write_private_files(directory, {"Caddyfile": caddy_config(public_ip, console=True)})
    _run(CONSOLE_COMPOSE + ["pull", "--quiet", "edge"], "Status edge download", 300)
    _run(CONSOLE_COMPOSE + ["up", "-d", "--no-deps", "edge"], "Status edge startup", 60)


def activate_gateway(directory):
    start_native_services(directory, compose=CONSOLE_COMPOSE)
    # Atomic host file replacement does not change an existing bind-mounted inode.
    _run(CONSOLE_COMPOSE + ["up", "-d", "--no-deps", "--force-recreate", "--wait",
                            "--wait-timeout", "180", "gateway"], "Provider credential activation", 240)

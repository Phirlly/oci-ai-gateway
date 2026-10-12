"""Creation-only Vault DNS/TLS readiness on the Resource Manager Unix runner."""

import os
import re
import signal
import socket
import ssl
import sys
import time

READINESS_SECONDS = 180


def validated_host(endpoint, region):
    if not re.fullmatch(r"[a-z]{2,}-[a-z0-9-]+-[0-9]+", region):
        raise ValueError("Invalid hosting region")
    pattern = (r"https://([a-z0-9][a-z0-9-]{0,50}-management\.kms\."
               + re.escape(region) + r"\.oraclecloud\.com)/?")
    match = re.fullmatch(pattern, endpoint)
    if match is None:
        raise ValueError("Invalid Vault management endpoint")
    return match.group(1)


def tls_context():
    # Unlike create_default_context, this never enables ambient SSLKEYLOGFILE.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    return context


def probe(host, *, budget=READINESS_SECONDS):
    """Only the test harness overrides budget; the stack has a fixed deadline."""
    if not 0 < budget <= READINESS_SECONDS:
        raise ValueError("Invalid readiness budget")
    print("Waiting for Vault DNS and verified TLS (maximum 180s). "
          "Alarm termination means the readiness deadline expired.", flush=True)
    handler = signal.signal(signal.SIGALRM, signal.SIG_DFL)
    mask = signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGALRM})
    signal.setitimer(signal.ITIMER_REAL, budget)
    try:
        deadline = time.monotonic() + budget
        context = tls_context()
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, 443), timeout=3) as connection:
                    with context.wrap_socket(connection, server_hostname=host):
                        return
            except ssl.SSLError:
                raise  # Certificate/protocol errors must never weaken TLS trust.
            except OSError:
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(2, remaining))
        raise TimeoutError("Vault endpoint deadline expired")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)


def main():
    try:
        host = validated_host(os.environ.get("VAULT_READINESS_ENDPOINT", ""),
                              os.environ.get("VAULT_READINESS_REGION", ""))
        probe(host)
    except ssl.SSLError:
        print("Vault readiness failed: TLS verification or handshake error.", file=sys.stderr)
        return 1
    except (ValueError, OSError, KeyboardInterrupt):
        print("Vault readiness failed: invalid endpoint, timeout or interruption.", file=sys.stderr)
        return 1
    print("Vault endpoint ready for key creation.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

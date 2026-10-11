"""Resume one Console run; persist uncertainty before any billed model requests."""

from datetime import datetime, timezone

from demo.verification import check_health, presenter_client, verify_demo

from .cloud_credentials import instance_id
from .console_credentials import console_inputs, internal_credentials, publish_credentials
from .console_secrets import read_secret
from .console_services import activate_gateway, start_edge
from .console_settings import load_context, runtime_settings, validate_console_settings
from .console_state import ConsoleState
from .console_status import publish_status
from .gateway_http import GatewayError, GatewayHTTP
from .presenter import Presenter, initialize_presenter
from .presenter_api import PresenterAPI
from .presenter_state import PresenterState
from .runtime_bundle import MODEL_ALIASES, RuntimeBundle
from .runtime_files import runtime_files, write_private_files


def _prepare(settings, context, directory, state, record):
    native = runtime_settings(settings)
    optional = settings["schema_version"] == 2
    inputs = console_inputs(settings, read_secret)
    if inputs is None:
        return None
    keys, password, versions = inputs
    field, unpinned = ("provider_versions", None) if optional else ("external_version", 0)
    if record[field] not in (unpinned, versions):
        raise GatewayError("Provider key changed during preparation; increase verification_run and Apply")
    record[field] = versions
    state.save(record)  # Desired version is durable before publishing/recreating anything.
    credentials = {**internal_credentials(directory), **keys}
    aliases = MODEL_ALIASES
    if optional:
        from .provider_selection import model_aliases
        aliases = model_aliases(native)
    presenter = Presenter(native["deployment_id"], native["presenter_email"], aliases)
    bundle = RuntimeBundle(native, context["public_ip"], credentials, presenter)
    files = runtime_files(bundle)
    del files["gateway-secrets.json"]
    del files["Caddyfile"]  # The independent edge already installed the Console config.
    write_private_files(directory, files)
    publish_credentials(directory, credentials, required_keys=set(keys))
    if record["phase"] == "preparing":
        activate_gateway(directory, native=not optional or "oci" in native["models"])
        record["phase"] = "active"
        state.save(record)
    public = GatewayHTTP("http://127.0.0.1:4000", allow_loopback=True)
    admin = GatewayHTTP(public.base_url, credentials["gateway_master_key"], allow_loopback=True)
    initialize_presenter(PresenterAPI(admin, public), PresenterState(directory, presenter),
                         presenter, password)
    return presenter, password


def run_console(settings, directory, status_directory):
    settings = validate_console_settings(settings)
    identity = instance_id(runtime_settings(settings))
    secret = read_secret(settings, context=True)
    context = load_context(secret.content, settings, identity)
    state = ConsoleState(directory, context, secret.identifier)
    record = state.begin()
    if record["phase"] in ("started", "complete"):
        phase = "INTERRUPTED" if record["phase"] == "started" else record["result"]
        publish_status(status_directory, phase, record)
        return
    publish_status(status_directory, "PREPARING", record)
    try:
        preparing = record["phase"] == "preparing"
        if preparing:
            start_edge(directory, context["public_ip"], native=settings["schema_version"] == 1 or "oci" in settings["runtime"]["models"])
        prepared = _prepare(settings, context, directory, state, record)
        if prepared is None:
            publish_status(status_directory, "WAITING_CREDENTIALS", record)
            return
        presenter, password = prepared
        if preparing and settings["schema_version"] == 2:
            return  # The next timer invocation owns the bounded billed workload.
        public = GatewayHTTP("https://" + context["public_ip"])
        try:
            # These bounded checks make no model requests and may safely retry.
            check_health(public)
            presenter_client(public, presenter, password)
        except (GatewayError, TimeoutError):
            publish_status(status_directory, "WAITING_FRONTEND", record)
            return
        record["phase"] = "started"
        state.save(record)
        publish_status(status_directory, "VERIFYING", record)
        report = verify_demo(public, presenter, password)
        samples = report["samples"]
        record["passed"] = sum(row["status"] == "PASS" for row in samples)
        ready = (len(samples) == state.total and record["passed"] == state.total and report["ready"]
                 and all(report[field] == "PASS" for field in ("login", "model_access", "admin_denial")))
        record["result"] = "READY" if ready else "FAILED"
    except (GatewayError, TimeoutError):
        if record["phase"] != "started":
            publish_status(status_directory, "ERROR", record)
            return  # Preparation is resumable; no model requests started.
        record["result"] = "ERROR"
    record["phase"] = "complete"
    record["finished_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.save(record)
    publish_status(status_directory, record["result"], record)

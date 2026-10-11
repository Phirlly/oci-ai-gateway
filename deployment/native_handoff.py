"""Publish native runtime credentials after one exact successful infrastructure Apply."""

from .apply_submission import ensure_apply
from .cloud_context import resolve_runtime_context
from .credential_errors import DeliveryError
from .foundation_history import recover_base
from .foundation_resources import vault_target
from .native_credentials import prepare_native_credentials
from .secret_delivery import SecretDelivery
from .stack_submission import ensure_stack


def advance_native_handoff(client, journal, target, package, *, vault, compute, inference_region,
                           external_api_key=None, demo_password=None, now=None):
    from .credential_handoff import FoundationHandoff
    settings = target.config.values
    if (vault is None or compute is None or vault.region != settings["region"]
            or compute.region != settings["region"] or inference_region != settings["inference_region"]):
        raise DeliveryError("Native handoff requires the configured hosting and inference regions.")
    stack = ensure_stack(client, journal, target, package)
    if stack.state != "ACTIVE":
        return FoundationHandoff("FOUNDATION", stack.stack_id, stack.state)
    job = ensure_apply(client, journal, target, package, stack.stack_id, model_key_ocid=None)
    if job.state != "SUCCEEDED":
        return FoundationHandoff("FOUNDATION", stack.stack_id, stack.state, job)
    stack, base = recover_base(client, journal, target, package, stack.stack_id)
    resources = client.list_job_resources(base.job_id, target.compartment_id)
    owned = vault_target(resources, target.config, stack.stack_id, inference_region)
    context = resolve_runtime_context(compute, resources, target.config)
    delivery = SecretDelivery(vault, owned, now=now)
    credentials = prepare_native_credentials(delivery, runtime_context=context,
                                             external_api_key=external_api_key, demo_password=demo_password)
    published = delivery.publish(credentials.version_name, None)
    return FoundationHandoff("CREDENTIALS_PUBLISHED", stack.stack_id, stack.state, base, published, context)

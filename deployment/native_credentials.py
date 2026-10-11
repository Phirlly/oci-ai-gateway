"""Prepare or recover the native deployment's one immutable credential bundle."""

import json
import secrets

from .credential_errors import DeliveryError
from .credential_records import parse_record
from .runtime_context import valid_runtime_context
from .vault_state import read_version


def prepare_native_credentials(delivery, *, runtime_context, external_api_key=None, demo_password=None):
    optional = "models" in delivery.target.identity
    if not valid_runtime_context(runtime_context, optional=optional):
        raise DeliveryError("Verified native runtime context is required.")
    receipt = delivery.reconcile()
    if receipt.phase == "UNCONFIGURED":
        supplied = (external_api_key if isinstance(external_api_key, dict) else {}) if optional else {"external_api_key": external_api_key}
        value = {"schema_version": 4 if optional else 3, "kind": "runtime-bundle",
                 "identity": dict(delivery.target.identity), "operation_id": secrets.token_hex(16),
                 "runtime": dict(runtime_context), "credentials": {
                     **supplied, "demo_password": demo_password,
                     "database_password": secrets.token_hex(24),
                     "gateway_master_key": "sk-" + secrets.token_hex(24),
                     "gateway_salt_key": secrets.token_hex(32)}}
        record = parse_record(json.dumps(value).encode(), dict(delivery.target.identity))
        receipt = delivery.stage(record)
    if receipt.phase not in {"PENDING", "CURRENT"} or receipt.model_key_ocid is not None:
        raise DeliveryError("Native deployment has incompatible saved credentials; preserve them for recovery.")
    version = read_version(delivery.client, delivery.target, delivery.now(), number=receipt.version_number)
    if (version.record is None or not version.record.is_native
            or version.name != receipt.version_name or receipt.phase not in version.stages
            or version.record.runtime_context != runtime_context):
        raise DeliveryError("Saved native credentials differ from the verified deployment.")
    current = delivery.reconcile()
    if current != receipt:
        raise DeliveryError("Native credentials changed during verification; reconcile before proceeding.")
    return receipt

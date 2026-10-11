"""Synthetic native inputs; legacy fixtures retain their original wire formats."""

from .gateway_config_fixture import GATEWAY_SETTINGS, CONTEXT
from .record_fixtures import IDENTITY

NATIVE_SETTINGS = {key: value for key, value in GATEWAY_SETTINGS.items() if key != "model_key_ttl_days"}
NATIVE_SETTINGS.update(schema_version=3, oci_model_id="google.gemini-2.5-flash-lite")


def native_document():
    return {"schema_version": 3, "kind": "runtime-bundle", "identity": dict(IDENTITY),
            "operation_id": "a" * 32, "runtime": dict(CONTEXT), "credentials": {
                "external_api_key": "synthetic-external", "database_password": "synthetic-database",
                "gateway_master_key": "sk-synthetic-master", "gateway_salt_key": "synthetic-salt",
                "demo_password": "Synthetic9!Password"}}

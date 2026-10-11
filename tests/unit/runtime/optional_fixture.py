"""Synthetic optional-provider settings and credentials, never live data."""

from itertools import combinations

MODELS = {"oci": "google.gemini-2.5-flash-lite", "anthropic": "claude-sonnet-4-6",
          "openai": "gpt-4.1-mini-2025-04-14"}
SUBSETS = tuple(group for size in (1, 2, 3) for group in combinations(MODELS, size))


def settings(providers=tuple(MODELS)):
    value = {"schema_version": 4, "deployment_id": "gateway-test",
             "tenancy_ocid": "ocid1.tenancy.oc1..synthetic",
             "compartment_ocid": "ocid1.compartment.oc1..synthetic",
             "secret_ocid": "ocid1.vaultsecret.oc1.iad.runtime", "region": "us-ashburn-1",
             "presenter_email": "presenter@example.invalid",
             "models": {name: MODELS[name] for name in providers}}
    if "oci" in providers:
        value["inference_region"] = "us-ashburn-1"
    return value


def credentials(providers=tuple(MODELS)):
    return {"database_password": "synthetic-database", "gateway_master_key": "sk-synthetic-master",
            "gateway_salt_key": "synthetic-salt", "demo_password": "Synthetic9!Password",
            **{name + "_api_key": "synthetic-" + name for name in providers if name != "oci"}}


INSTANCE = "ocid1.instance.oc1.iad.synthetic"


def document(providers):
    value = settings(providers)
    identity = {key: item for key, item in value.items()
                if key not in {"region", "presenter_email", "schema_version"}}
    identity["stack_ocid"] = "ocid1.ormstack.oc1.iad.synthetic"
    return {"schema_version": 4, "kind": "runtime-bundle", "operation_id": "a" * 32,
            "identity": identity, "credentials": credentials(providers),
            "runtime": {"instance_ocid": INSTANCE, "public_ip": "8.8.4.4",
                        "public_ip_ocid": "ocid1.publicip.oc1.iad.synthetic",
                        "presenter_email": value["presenter_email"]}}

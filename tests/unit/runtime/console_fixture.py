"""Synthetic Console contracts; never real deployment identifiers or credentials."""

def settings():
    return {"schema_version": 1, "vault_ocid": "ocid1.vault.oc1.iad.synthetic",
            "presenter_secret_ocid": "ocid1.vaultsecret.oc1.iad.presenter",
            "context_name": "gateway-test-context", "native": {
                "schema_version": 3, "deployment_id": "gateway-test",
                "tenancy_ocid": "ocid1.tenancy.oc1..synthetic",
                "compartment_ocid": "ocid1.compartment.oc1..synthetic",
                "secret_ocid": "ocid1.vaultsecret.oc1.iad.external", "region": "us-ashburn-1",
                "inference_region": "us-ashburn-1", "model_id": "example.model",
                "presenter_email": "presenter@example.invalid", "external_provider": "anthropic",
                "external_model_id": "example-model"}}


def context(run=1):
    return {"schema_version": 1, "settings": settings(), "verification_run": run,
            "instance_ocid": "ocid1.instance.oc1.iad.synthetic",
            "public_ip_ocid": "ocid1.publicip.oc1.iad.synthetic", "public_ip": "8.8.4.4"}

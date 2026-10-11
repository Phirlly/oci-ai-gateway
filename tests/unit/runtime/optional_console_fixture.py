"""Synthetic direct-Console settings for any enabled provider subset."""

from .optional_fixture import MODELS, settings as runtime_settings


def settings(providers=tuple(MODELS)):
    return {"schema_version": 2, "runtime": runtime_settings(providers),
            "vault_ocid": "ocid1.vault.oc1.iad.synthetic",
            "presenter_secret_ocid": "ocid1.vaultsecret.oc1.iad.presenter",
            "context_name": "gateway-test-context",
            "provider_secrets": {p: "ocid1.vaultsecret.oc1.iad." + p for p in providers if p != "oci"}}


def context(providers=tuple(MODELS), run=1):
    return {"schema_version": 1, "settings": settings(providers), "verification_run": run,
            "instance_ocid": "ocid1.instance.oc1.iad.synthetic",
            "public_ip_ocid": "ocid1.publicip.oc1.iad.synthetic", "public_ip": "8.8.4.4"}

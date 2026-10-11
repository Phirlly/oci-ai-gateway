"""Native wire inputs derived from the unchanged legacy ownership fixture."""

from .bundle_fixture import SETTINGS, bundle

NATIVE_SETTINGS = SETTINGS | {"schema_version": 3}


def native_bundle():
    value = bundle()
    value["schema_version"] = 3
    del value["expires_at"], value["model_key_ocid"], value["credentials"]["oci_api_key"]
    return value

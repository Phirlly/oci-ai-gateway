"""The two configured routes; no service credentials or live identity."""


def gateway_config():
    return {"model_list": [
        {"model_name": "oci-managed", "litellm_params": {
            "model": "oci/google.gemini-2.5-flash-lite", "oci_region": "us-ashburn-1",
            "oci_compartment_id": "ocid1.compartment.oc1..synthetic",
            "additional_drop_params": ["stream_options"], "max_tokens": 32, "num_retries": 0,
        }},
        {"model_name": "external-anthropic", "litellm_params": {
            "model": "anthropic/claude-sonnet-4-6", "api_key": "os.environ/ANTHROPIC_API_KEY",
        }},
    ]}

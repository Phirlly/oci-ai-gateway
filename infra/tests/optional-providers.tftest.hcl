mock_provider "oci" {
  source          = "./tests/fixtures"
  override_during = plan
}
mock_provider "oci" {
  alias           = "home"
  source          = "./tests/fixtures"
  override_during = plan
}
variables {
  tenancy_ocid               = "ocid1.tenancy.oc1..aaaaaaaaexampletenancy"
  compartment_ocid           = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment"
  region                     = "us-ashburn-1"
  deployment_id              = "gateway-optional"
  schema_version             = 4
  models                     = { openai = "gpt-4.1-mini-2025-04-14" }
  presenter_email            = "presenter@example.invalid"
  instance_shape             = "VM.Standard.E4.Flex"
  instance_ocpus             = 1
  instance_memory_gbs        = 8
  boot_volume_size_gbs       = 50
  availability_domain_number = 1
  image_name                 = "Canonical-Ubuntu-24.04-2026.09.18-0"
}
run "external_only_has_no_native_authority_or_fake_scope" {
  command = plan
  assert {
    condition     = length(oci_identity_policy.native_chat) == 0 && length(oci_identity_policy.model_chat) == 0
    error_message = "External-only must grant no inference permissions."
  }
  assert {
    condition     = local.runtime_settings.schema_version == 4 && local.runtime_settings.models == var.models && !can(local.runtime_settings.inference_region) && !can(local.runtime_settings.model_id)
    error_message = "Optional settings contain only the selected models and no invented native scope."
  }
  assert {
    condition     = length(oci_core_instance.gateway.metadata.user_data) < 16000
    error_message = "Optional bootstrap must fit the metadata budget."
  }
}
run "oci_only_has_exact_native_authority" {
  command = plan
  variables {
    models           = { oci = "google.gemini-2.5-flash-lite" }
    inference_region = "us-ashburn-1"
  }
  assert {
    condition     = length(oci_identity_policy.native_chat) == 1 && strcontains(one(oci_identity_policy.native_chat).statements[0], "target.model.id='${var.models.oci}'") && local.runtime_settings.inference_region == var.inference_region
    error_message = "Only the selected OCI model receives native authorization."
  }
}
run "three_providers_keep_one_native_policy" {
  command = plan
  variables {
    models           = { oci = "google.gemini-2.5-flash-lite", anthropic = "claude-sonnet-4-6", openai = "gpt-4.1-mini-2025-04-14" }
    inference_region = "us-ashburn-1"
  }
  assert {
    condition     = length(local.runtime_settings.models) == 3 && length(oci_identity_policy.native_chat) == 1
    error_message = "Adding external models must not broaden native IAM."
  }
}
run "empty_selection_fails" {
  command = plan
  variables { models = {} }
  expect_failures = [oci_core_instance.gateway]
}
run "external_only_rejects_unused_inference_region" {
  command = plan
  variables { inference_region = "us-chicago-1" }
  expect_failures = [oci_core_instance.gateway]
}

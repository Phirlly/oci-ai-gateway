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
  deployment_id              = "gateway-test"
  oci_model_id               = "example.chat-model"
  schema_version             = 3
  inference_region           = "us-ashburn-1"
  external_provider          = "anthropic"
  external_model_id          = "synthetic-external"
  presenter_email            = "presenter@example.invalid"
  instance_shape             = "VM.Standard.E4.Flex"
  instance_ocpus             = 1
  instance_memory_gbs        = 8
  boot_volume_size_gbs       = 50
  availability_domain_number = 1
  image_name                 = "Canonical-Ubuntu-24.04-2026.09.18-0"
}
run "native_identity_and_metadata_are_scoped" {
  command = plan
  assert {
    condition = length(oci_identity_policy.model_chat) == 0 && one(oci_identity_policy.native_chat).statements == tolist([
      "Allow any-user to use generative-ai-chat in compartment id ${var.compartment_ocid} where all {request.principal.type='instance', request.instance.id='${oci_core_instance.gateway.id}', target.model.id='${var.oci_model_id}'}"
    ])
    error_message = "Native inference belongs only to this instance, compartment and model; no bearer grant."
  }
  assert {
    condition     = length(oci_core_instance.gateway.metadata.user_data) < 16000 && oci_core_instance.gateway.metadata.user_data == base64gzip(local.cloud_init)
    error_message = "The complete compressed user_data must fit the metadata limit."
  }
  assert {
    condition     = local.runtime_settings.schema_version == 3 && yamldecode(local.cloud_init).write_files[3].path == "/etc/oci-ai-gateway-source.json" && jsondecode(yamldecode(local.cloud_init).write_files[3].content).commit != ""
    error_message = "Native deployment requires its retained source manifest and matching private settings."
  }
  assert {
    condition     = contains(local.native_bootstrap_assets, "runtime/systemd/oci-ai-gateway-native-bootstrap.service") && contains(local.native_bootstrap_assets, "runtime/systemd/oci-ai-gateway-bootstrap.timer") && !contains(local.native_bootstrap_assets, "runtime/bootstrap.py")
    error_message = "The source verification service and retry timer must be embedded before downloads."
  }
}
run "native_rejects_model_key_binding" {
  command = plan
  variables { oci_model_key_ocid = "ocid1.generativeaiapikey.oc1.iad.synthetic" }
  expect_failures = [oci_core_instance.gateway]
}

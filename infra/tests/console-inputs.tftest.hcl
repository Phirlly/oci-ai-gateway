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
  console_image_ocid         = "ocid1.image.oc1.iad.retained"
  console_ad_name            = "synthetic:US-ASHBURN-AD-1"
  console_cloud_init         = "#cloud-config\n{}\n"
}
run "console_retains_selected_image_and_uses_its_bootstrap" {
  command = plan
  override_resource {
    target          = oci_core_public_ip.gateway
    override_during = plan
    values          = { ip_address = "8.8.4.4" }
  }
  assert {
    condition     = oci_core_instance.gateway.source_details[0].source_id == var.console_image_ocid
    error_message = "Console image OCID must survive catalog changes."
  }
  assert {
    condition     = oci_core_instance.gateway.metadata.user_data == base64gzip(var.console_cloud_init)
    error_message = "Console bootstrap must replace the controller bootstrap."
  }
  assert {
    condition     = output.instance_ocid == oci_core_instance.gateway.id && output.public_ip == oci_core_public_ip.gateway.ip_address
    error_message = "Only the full Compute module should export instance and IP identity."
  }
}

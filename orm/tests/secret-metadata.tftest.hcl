mock_provider "oci" {
  source          = "../infra/tests/fixtures"
  override_during = plan
  mock_data "oci_core_image" {
    defaults = { display_name = "Canonical-Ubuntu-24.04-2026.09.18-0", operating_system = "Canonical Ubuntu", operating_system_version = "24.04" }
  }
}
mock_provider "oci" {
  alias           = "home"
  source          = "../infra/tests/fixtures"
  override_during = plan
}
override_module {
  target = module.gateway
  outputs = {
    home_region      = "us-ashburn-1", runtime_vault_ocid = "ocid1.vault.oc1.iad.synthetic",
    runtime_key_ocid = "ocid1.key.oc1.iad.synthetic", runtime_secret_ocid = "ocid1.vaultsecret.oc1.iad.unused",
    instance_ocid    = "ocid1.instance.oc1.iad.synthetic", public_ip = "8.8.4.4", public_ip_ocid = "ocid1.publicip.oc1.iad.synthetic"
  }
}
variables {
  tenancy_ocid          = "ocid1.tenancy.oc1..aaaaaaaaexampletenancy"
  compartment_ocid      = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment"
  region                = "us-ashburn-1"
  deployment_id         = "gateway-console"
  image_ocid            = "ocid1.image.oc1.iad.retained"
  availability_domain   = "synthetic:US-ASHBURN-AD-1"
  enable_anthropic      = true
  anthropic_secret_ocid = "ocid1.vaultsecret.oc1.iad.sharedanthropic"
}
run "reject_secret_from_another_compartment" {
  command = plan
  override_data {
    target = data.oci_vault_secret.existing_provider["anthropic"]
    values = { id = "ocid1.vaultsecret.oc1.iad.sharedanthropic", compartment_id = "ocid1.compartment.oc1..other", state = "ACTIVE" }
  }
  expect_failures = [data.oci_vault_secret.existing_provider]
}
run "reject_secret_pending_deletion" {
  command = plan
  override_data {
    target = data.oci_vault_secret.existing_provider["anthropic"]
    values = { id = "ocid1.vaultsecret.oc1.iad.sharedanthropic", compartment_id = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment", state = "PENDING_DELETION" }
  }
  expect_failures = [data.oci_vault_secret.existing_provider]
}
run "reject_mismatched_metadata_id" {
  command = plan
  override_data {
    target = data.oci_vault_secret.existing_provider["anthropic"]
    values = { id = "ocid1.vaultsecret.oc1.iad.different", compartment_id = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment", state = "ACTIVE" }
  }
  expect_failures = [data.oci_vault_secret.existing_provider]
}

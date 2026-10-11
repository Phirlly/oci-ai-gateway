# The shared module owns the infrastructure; this root owns the Console journey.
module "gateway" {
  source = "../infra"

  tenancy_ocid               = var.tenancy_ocid
  compartment_ocid           = var.compartment_ocid
  region                     = var.region
  deployment_id              = var.deployment_id
  schema_version             = 3
  oci_model_id               = var.oci_model_id
  inference_region           = coalesce(var.inference_region, var.region)
  external_provider          = "anthropic"
  external_model_id          = var.external_model_id
  presenter_email            = var.presenter_email
  instance_shape             = var.instance_shape
  instance_ocpus             = var.instance_ocpus
  instance_memory_gbs        = var.instance_memory_gbs
  boot_volume_size_gbs       = 80
  availability_domain_number = 1
  image_name                 = data.oci_core_image.selected.display_name
  console_image_ocid         = var.image_ocid
  console_ad_name            = var.availability_domain
  console_cloud_init         = local.cloud_init
}

data "oci_core_image" "selected" {
  image_id = var.image_ocid
  lifecycle {
    postcondition {
      condition     = self.operating_system == "Canonical Ubuntu" && self.operating_system_version == "24.04" && can(regex("^Canonical-Ubuntu-24\\.04-[0-9]{4}\\.[0-9]{2}\\.[0-9]{2}-[0-9]+$", self.display_name))
      error_message = "Select a regional Canonical Ubuntu24.04 AMD image compatible with the selected shape."
    }
  }
}

locals {
  tags = { solution = "oci-ai-gateway-lab", deployment_id = var.deployment_id }
  native_settings = {
    schema_version    = 3
    deployment_id     = var.deployment_id
    tenancy_ocid      = var.tenancy_ocid
    compartment_ocid  = var.compartment_ocid
    region            = var.region
    inference_region  = coalesce(var.inference_region, var.region)
    model_id          = var.oci_model_id
    external_provider = "anthropic"
    external_model_id = var.external_model_id
    presenter_email   = var.presenter_email
    secret_ocid       = module.gateway.runtime_secret_ocid
  }
  console_settings = {
    schema_version        = 1
    native                = local.native_settings
    vault_ocid            = module.gateway.runtime_vault_ocid
    presenter_secret_ocid = oci_vault_secret.presenter.id
    context_name          = "${var.deployment_id}-context"
  }
}

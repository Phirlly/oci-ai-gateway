# The shared module owns the infrastructure; this root owns the Console journey.
module "gateway" {
  source = "../infra"

  tenancy_ocid               = var.tenancy_ocid
  compartment_ocid           = var.compartment_ocid
  region                     = var.region
  deployment_id              = var.deployment_id
  schema_version             = 4
  models                     = local.models
  inference_region           = var.enable_oci ? coalesce(var.inference_region, var.region) : null
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
  console_mode               = true
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
  models = merge(
    var.enable_oci ? { oci = var.oci_model_id } : {},
    var.enable_anthropic ? { anthropic = var.anthropic_model_id } : {},
    var.enable_openai ? { openai = var.openai_model_id } : {},
  )
  runtime_settings = merge({
    schema_version   = 4
    deployment_id    = var.deployment_id
    tenancy_ocid     = var.tenancy_ocid
    compartment_ocid = var.compartment_ocid
    region           = var.region
    models           = local.models
    presenter_email  = var.presenter_email
    secret_ocid      = module.gateway.runtime_secret_ocid
  }, var.enable_oci ? { inference_region = coalesce(var.inference_region, var.region) } : {})
  console_settings = {
    schema_version        = 2
    runtime               = local.runtime_settings
    provider_secrets      = local.provider_secret_ids
    vault_ocid            = module.gateway.runtime_vault_ocid
    presenter_secret_ocid = oci_vault_secret.presenter.id
    context_name          = "${var.deployment_id}-context"
  }
}

variable "anthropic_secret_ocid" {
  type        = string
  default     = ""
  nullable    = false
  description = "Optional saved Anthropic secret in the deployment compartment and hosting region. Blank creates an owned placeholder. Keep this selection unchanged."
  validation {
    condition     = var.anthropic_secret_ocid == "" || (length(var.anthropic_secret_ocid) <= 512 && can(regex("^ocid1\\.vaultsecret\\.oc1\\.[a-z0-9-]+\\.[a-zA-Z0-9._-]+$", var.anthropic_secret_ocid)))
    error_message = "Select an OC1 Vault secret OCID, not an API key, or leave blank."
  }
}

variable "openai_secret_ocid" {
  type        = string
  default     = ""
  nullable    = false
  description = "Optional saved OpenAI secret in the deployment compartment and hosting region. Blank creates an owned placeholder. Keep this selection unchanged."
  validation {
    condition     = var.openai_secret_ocid == "" || (length(var.openai_secret_ocid) <= 512 && can(regex("^ocid1\\.vaultsecret\\.oc1\\.[a-z0-9-]+\\.[a-zA-Z0-9._-]+$", var.openai_secret_ocid)))
    error_message = "Select an OC1 Vault secret OCID, not an API key, or leave blank."
  }
}

locals {
  existing_provider_secret_ids = { for provider, id in {
    anthropic = var.anthropic_secret_ocid, openai = var.openai_secret_ocid
  } : provider => id if id != "" }
  provider_secret_ids = merge(
    { for provider, secret in oci_vault_secret.provider : provider => secret.id },
    { for provider, secret in data.oci_vault_secret.existing_provider : provider => secret.id },
  )
}

# GetSecret returns metadata only. Contents are read by the VM, never Terraform.
# These references do not transfer ownership of caller-managed secrets.
data "oci_vault_secret" "existing_provider" {
  for_each  = local.existing_provider_secret_ids
  secret_id = each.value
  lifecycle {
    precondition {
      condition     = contains(keys(local.models), each.key)
      error_message = "A saved provider secret requires its provider to be enabled. Clear unused selections."
    }
    precondition {
      condition     = length(distinct(values(local.existing_provider_secret_ids))) == length(local.existing_provider_secret_ids)
      error_message = "Select a different secret for each external provider."
    }
    postcondition {
      condition     = self.id == each.value && self.compartment_id == var.compartment_ocid && self.state == "ACTIVE"
      error_message = "Select an ACTIVE secret in the deployment compartment and hosting region."
    }
  }
}

# Keep this address and blank-input behavior for existing Console deployments.
resource "oci_vault_secret" "provider" {
  for_each       = { for provider, model in local.models : provider => model if provider != "oci" && !contains(keys(local.existing_provider_secret_ids), provider) }
  compartment_id = var.compartment_ocid
  vault_id       = module.gateway.runtime_vault_ocid
  key_id         = module.gateway.runtime_key_ocid
  secret_name    = "${var.deployment_id}-${each.key}"
  freeform_tags  = local.tags
  secret_content {
    content_type = "BASE64"
    name         = "unconfigured"
    stage        = "CURRENT"
    content      = base64encode("UNCONFIGURED")
  }
  lifecycle {
    ignore_changes = [secret_content]
  }
}

resource "oci_kms_vault" "runtime" {
  compartment_id = var.compartment_ocid
  display_name   = "${var.deployment_id}-runtime"
  vault_type     = "DEFAULT"
  freeform_tags  = local.ownership_tags

  depends_on = [data.oci_identity_region_subscriptions.tenancy]
}

# Creation-only: a new Vault can be ACTIVE before its endpoint resolves.
# Default-null keeps existing controller archive layouts and recovery intact.
resource "terraform_data" "vault_endpoint" {
  count            = var.vault_readiness_script_path == null ? 0 : 1
  triggers_replace = oci_kms_vault.runtime.id
  input = {
    endpoint = oci_kms_vault.runtime.management_endpoint
    region   = var.region
  }

  provisioner "local-exec" {
    interpreter = ["python3", "-I", "-B"]
    command     = var.vault_readiness_script_path
    environment = {
      VAULT_READINESS_ENDPOINT = self.input.endpoint
      VAULT_READINESS_REGION   = self.input.region
    }
  }
}

resource "oci_kms_key" "runtime" {
  depends_on          = [terraform_data.vault_endpoint]
  compartment_id      = var.compartment_ocid
  display_name        = "${var.deployment_id}-runtime"
  management_endpoint = oci_kms_vault.runtime.management_endpoint
  protection_mode     = "HSM"
  freeform_tags       = local.ownership_tags

  key_shape {
    algorithm = "AES"
    length    = 32
  }
}

resource "oci_vault_secret" "runtime" {
  compartment_id = var.compartment_ocid
  vault_id       = oci_kms_vault.runtime.id
  key_id         = oci_kms_key.runtime.id
  secret_name    = "${var.deployment_id}-runtime"
  freeform_tags  = local.ownership_tags

  secret_content {
    content_type = "BASE64"
    content      = base64encode("UNCONFIGURED")
    name         = "unconfigured"
    stage        = "CURRENT"
  }

  lifecycle {
    # Deployment workflow owns real contents and version promotion outside
    # Terraform. current_version_number is computed-only in provider 9.8.0.
    ignore_changes = [secret_content]
  }
}

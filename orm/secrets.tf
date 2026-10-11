resource "oci_vault_secret" "presenter" {
  compartment_id         = var.compartment_ocid
  vault_id               = module.gateway.runtime_vault_ocid
  key_id                 = module.gateway.runtime_key_ocid
  secret_name            = "${var.deployment_id}-presenter"
  freeform_tags          = local.tags
  enable_auto_generation = true
  secret_generation_context {
    generation_type     = "PASSPHRASE"
    generation_template = "SECRETS_DEFAULT_PASSWORD"
    passphrase_length   = 32
    secret_template     = jsonencode({ password = "Demo1!%GENERATED_PASSPHRASE%" })
  }
}

# Only nonsecret configuration and a run counter enter Terraform content/state.
resource "oci_vault_secret" "context" {
  compartment_id = var.compartment_ocid
  vault_id       = module.gateway.runtime_vault_ocid
  key_id         = module.gateway.runtime_key_ocid
  secret_name    = local.console_settings.context_name
  freeform_tags  = local.tags
  secret_content {
    content_type = "BASE64"
    stage        = "CURRENT"
    content = base64encode(jsonencode({
      schema_version   = 1
      settings         = local.console_settings
      instance_ocid    = module.gateway.instance_ocid
      public_ip        = module.gateway.public_ip
      public_ip_ocid   = module.gateway.public_ip_ocid
      verification_run = var.verification_run
    }))
  }
}

resource "oci_identity_policy" "console_secrets" {
  provider       = oci.home
  compartment_id = var.compartment_ocid
  name           = "${var.deployment_id}-console-read"
  description    = "Only this instance may read its presenter and nonsecret Console context."
  freeform_tags  = local.tags
  statements = [
    "Allow any-user to read secret-bundles in compartment id ${var.compartment_ocid} where all {request.principal.type='instance', request.instance.id='${module.gateway.instance_ocid}', target.secret.id='${oci_vault_secret.presenter.id}', request.operation='GetSecretBundle'}",
    "Allow any-user to read secret-bundles in compartment id ${var.compartment_ocid} where all {request.principal.type='instance', request.instance.id='${module.gateway.instance_ocid}', target.secret.id='${oci_vault_secret.context.id}', request.operation='GetSecretBundleByName'}",
  ]
}

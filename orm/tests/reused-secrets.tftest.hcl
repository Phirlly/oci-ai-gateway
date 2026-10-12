mock_provider "oci" {
  source          = "../infra/tests/fixtures"
  override_during = plan
  mock_data "oci_core_image" {
    defaults = { display_name = "Canonical-Ubuntu-24.04-2026.09.18-0", operating_system = "Canonical Ubuntu", operating_system_version = "24.04" }
  }
  mock_data "oci_vault_secret" {
    defaults = { compartment_id = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment", state = "ACTIVE" }
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
override_data {
  target = data.oci_vault_secret.existing_provider["anthropic"]
  values = { id = "ocid1.vaultsecret.oc1.iad.sharedanthropic", compartment_id = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment", state = "ACTIVE" }
}
override_data {
  target = data.oci_vault_secret.existing_provider["openai"]
  values = { id = "ocid1.vaultsecret.oc1.iad.sharedopenai", compartment_id = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment", state = "ACTIVE" }
}
variables {
  tenancy_ocid          = "ocid1.tenancy.oc1..aaaaaaaaexampletenancy"
  compartment_ocid      = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment"
  region                = "us-ashburn-1"
  deployment_id         = "gateway-console"
  image_ocid            = "ocid1.image.oc1.iad.retained"
  availability_domain   = "synthetic:US-ASHBURN-AD-1"
  enable_anthropic      = true
  enable_openai         = true
  anthropic_secret_ocid = "ocid1.vaultsecret.oc1.iad.sharedanthropic"
  openai_secret_ocid    = "ocid1.vaultsecret.oc1.iad.sharedopenai"
}
run "saved_keys_are_referenced_without_owned_provider_secrets" {
  command = plan
  assert {
    condition     = length(oci_vault_secret.provider) == 0 && length(data.oci_vault_secret.existing_provider) == 2
    error_message = "Saved provider secrets must be data references, never resources owned by this stack."
  }
  assert {
    condition = (
      local.console_settings.provider_secrets == { anthropic = var.anthropic_secret_ocid, openai = var.openai_secret_ocid } &&
      jsondecode(base64decode(oci_vault_secret.context.secret_content[0].content)).settings.provider_secrets == local.console_settings.provider_secrets
    )
    error_message = "Installed settings and late context must use exactly the selected secret IDs."
  }
  assert {
    condition = length(oci_identity_policy.console_secrets.statements) == 4 && alltrue([
      for id in [var.anthropic_secret_ocid, var.openai_secret_ocid] : contains(
        oci_identity_policy.console_secrets.statements,
        "Allow any-user to read secret-bundles in compartment id ${var.compartment_ocid} where all {request.principal.type='instance', request.instance.id='${module.gateway.instance_ocid}', target.secret.id='${id}', request.operation='GetSecretBundle'}"
      )
    ])
    error_message = "Saved-secret IAM must restrict each read to this instance and exact secret ID."
  }
  assert {
    condition = (
      output.anthropic_key_secret_url == "https://cloud.oracle.com/security/secrets/${var.anthropic_secret_ocid}?region=${var.region}" &&
      output.openai_key_secret_url == "https://cloud.oracle.com/security/secrets/${var.openai_secret_ocid}?region=${var.region}"
    )
    error_message = "Credential links must resolve to the selected saved secrets."
  }
}
run "mixed_saved_and_owned_credentials_keep_legacy_address" {
  command = plan
  variables { openai_secret_ocid = "" }
  assert {
    condition     = toset(keys(oci_vault_secret.provider)) == toset(["openai"]) && toset(keys(data.oci_vault_secret.existing_provider)) == toset(["anthropic"])
    error_message = "Only the provider without a saved secret should get an owned placeholder."
  }
  assert {
    condition     = base64decode(oci_vault_secret.provider["openai"].secret_content[0].content) == "UNCONFIGURED" && local.console_settings.provider_secrets.openai == oci_vault_secret.provider["openai"].id
    error_message = "Blank selection must preserve harmless placeholder behavior and address."
  }
}
run "selectors_are_optional_and_scoped_to_enabled_provider" {
  command = plan
  assert {
    condition = alltrue([for provider in keys(local.console_settings.provider_secrets) :
      yamldecode(file("schema.yaml")).variables["${provider}_secret_ocid"].type == "oci:kms:secret:id" &&
      yamldecode(file("schema.yaml")).variables["${provider}_secret_ocid"].dependsOn.compartmentId == "$${compartment_ocid}" &&
      yamldecode(file("schema.yaml")).variables["${provider}_secret_ocid"].visible == "$${enable_${provider}}" &&
      !yamldecode(file("schema.yaml")).variables["${provider}_secret_ocid"].required
    ])
    error_message = "Console must offer optional saved-secret selectors only for enabled providers in this compartment."
  }
}
run "saved_openai_only_needs_no_other_credentials" {
  command = plan
  variables {
    enable_oci            = false
    enable_anthropic      = false
    anthropic_secret_ocid = ""
  }
  assert {
    condition = (
      length(oci_vault_secret.provider) == 0 &&
      local.console_settings.provider_secrets == { openai = var.openai_secret_ocid } &&
      length(oci_identity_policy.console_secrets.statements) == 3 &&
      output.anthropic_key_secret_url == null && !can(local.runtime_settings.inference_region)
    )
    error_message = "An external-only saved-key deployment must not require OCI inference or disabled provider keys."
  }
}

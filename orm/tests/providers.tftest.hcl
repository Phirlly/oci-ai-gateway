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
    home_region         = "us-ashburn-1"
    runtime_vault_ocid  = "ocid1.vault.oc1.iad.synthetic"
    runtime_key_ocid    = "ocid1.key.oc1.iad.synthetic"
    runtime_secret_ocid = "ocid1.vaultsecret.oc1.iad.unused"
    instance_ocid       = "ocid1.instance.oc1.iad.synthetic"
    public_ip           = "8.8.4.4"
    public_ip_ocid      = "ocid1.publicip.oc1.iad.synthetic"
  }
}
variables {
  tenancy_ocid        = "ocid1.tenancy.oc1..aaaaaaaaexampletenancy"
  compartment_ocid    = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment"
  region              = "us-ashburn-1"
  deployment_id       = "gateway-console"
  image_ocid          = "ocid1.image.oc1.iad.retained"
  availability_domain = "synthetic:US-ASHBURN-AD-1"
}
run "default_oci_only_needs_no_external_secrets" {
  command = plan
  assert {
    condition     = toset(keys(local.models)) == toset(["oci"]) && length(oci_vault_secret.provider) == 0 && output.anthropic_key_secret_url == null && output.openai_key_secret_url == null
    error_message = "Default OCI-only deploy must require no external account/key."
  }
  assert {
    condition     = local.console_settings.schema_version == 2 && length(local.console_settings.provider_secrets) == 0 && length(oci_identity_policy.console_secrets.statements) == 2
    error_message = "Console settings/IAM must cover only selected credentials."
  }
}
run "openai_only_omits_native_scope" {
  command = plan
  variables {
    enable_oci    = false
    enable_openai = true
  }
  assert {
    condition     = toset(keys(local.models)) == toset(["openai"]) && toset(keys(oci_vault_secret.provider)) == toset(["openai"]) && !can(local.runtime_settings.inference_region) && output.anthropic_key_secret_url == null
    error_message = "OpenAI-only must not carry fabricated native inference settings or Anthropic credentials."
  }
}
run "all_providers_have_separate_placeholders_and_exact_read_iam" {
  command = plan
  variables {
    enable_anthropic = true
    enable_openai    = true
  }
  assert {
    condition     = length(local.models) == 3 && length(oci_vault_secret.provider) == 2 && alltrue([for secret in oci_vault_secret.provider : base64decode(secret.secret_content[0].content) == "UNCONFIGURED"])
    error_message = "Only harmless placeholders may enter Terraform."
  }
  assert {
    condition     = length(oci_identity_policy.console_secrets.statements) == 4 && alltrue([for statement in oci_identity_policy.console_secrets.statements : strcontains(statement, "request.instance.id='${module.gateway.instance_ocid}'") && strcontains(statement, "target.secret.id='")])
    error_message = "Every secret read must target the exact instance and one selected secret."
  }
}

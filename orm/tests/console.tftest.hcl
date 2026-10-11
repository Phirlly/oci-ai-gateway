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
variables {
  tenancy_ocid        = "ocid1.tenancy.oc1..aaaaaaaaexampletenancy"
  compartment_ocid    = "ocid1.compartment.oc1..aaaaaaaaexamplecompartment"
  region              = "us-ashburn-1"
  deployment_id       = "gateway-console"
  image_ocid          = "ocid1.image.oc1.iad.retained"
  availability_domain = "synthetic:US-ASHBURN-AD-1"
  anthropic_model_id  = "synthetic-external"
  presenter_email     = "presenter@example.invalid"
}
run "console_context_credentials_and_outputs" {
  command = plan
  # infra has its own provider configurations and separate mock-plan suite.
  # This tests the Console boundary; composed validate checks the real graph.
  override_module {
    target = module.gateway
    outputs = {
      home_region         = "us-ashburn-1"
      runtime_vault_ocid  = "ocid1.vault.oc1.iad.synthetic"
      runtime_key_ocid    = "ocid1.key.oc1.iad.synthetic"
      runtime_secret_ocid = "ocid1.vaultsecret.oc1.iad.external"
      instance_ocid       = "ocid1.instance.oc1.iad.synthetic"
      public_ip           = "8.8.4.4"
      public_ip_ocid      = "ocid1.publicip.oc1.iad.synthetic"
    }
  }
  override_resource {
    target          = oci_vault_secret.presenter
    override_during = plan
    values          = { id = "ocid1.vaultsecret.oc1.iad.presenter" }
  }
  override_resource {
    target          = oci_vault_secret.context
    override_during = plan
    values          = { id = "ocid1.vaultsecret.oc1.iad.context" }
  }
  assert {
    condition     = var.oci_model_id == jsondecode(file("../deployment.tfvars.json.example")).models.oci
    error_message = "Console and GitHub defaults must use the same validated model."
  }
  assert {
    condition     = jsondecode(base64decode(oci_vault_secret.context.secret_content[0].content)).instance_ocid == module.gateway.instance_ocid
    error_message = "Late context must use the actual module instance."
  }
  assert {
    condition     = local.console_settings.context_name == "gateway-console-context" && !can(local.console_settings.context_secret_ocid)
    error_message = "Bootstrap discovers context by name to avoid a VM/context dependency cycle."
  }
  assert {
    condition     = oci_vault_secret.presenter.enable_auto_generation && length(oci_vault_secret.presenter.secret_content) == 0
    error_message = "Password generation is server-side, without Terraform secret content."
  }
  assert {
    condition     = length(base64gzip(local.cloud_init)) < 16000 && output.status_url == "https://8.8.4.4/deployment-status"
    error_message = "Embedded bootstrap must fit OCI limits and expose an independent status URL."
  }
  assert {
    condition     = length(oci_identity_policy.console_secrets.statements) == 2 && alltrue([for statement in oci_identity_policy.console_secrets.statements : strcontains(statement, "request.instance.id='${module.gateway.instance_ocid}'") && strcontains(statement, "target.secret.id='")])
    error_message = "Additional secret reads must be restricted to this exact instance and secrets."
  }
  assert {
    condition     = output.compare_url == "https://8.8.4.4/ui/playground/?tab=compare" && yamldecode(file("schema.yaml")).variables.image_ocid.type == "oci:core:image:id" && yamldecode(file("schema.yaml")).primaryOutputButton == "$${status_url}"
    error_message = "Console must expose the actual Compare route, image selector and status button."
  }
}

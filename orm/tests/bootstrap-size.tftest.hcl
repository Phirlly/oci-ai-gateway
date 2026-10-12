# Use distinct, full-length synthetic identifiers: short mock IDs hide overhead.
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
    runtime_vault_ocid  = "ocid1.vault.oc1.iad.synthetic.29a56b08e94630dc15bb2c93a4ee471d06c5f8729ac1048d3769feb065dd8012"
    runtime_key_ocid    = "ocid1.key.oc1.iad.synthetic.934b8f0137559dc2ea19743011c078f20246612dbe5569fcd3aa916039007a55"
    runtime_secret_ocid = "ocid1.vaultsecret.oc1.iad.14f0c29bae54618d776245790ac432ef88eb0263e9b561a7358f903d40c2e76a"
    instance_ocid       = "ocid1.instance.oc1.iad.692a001965ac3849e40c23f71b96d0ae2055808bd12fe473ce9905f88bc15673"
    public_ip           = "192.0.2.123"
    public_ip_ocid      = "ocid1.publicip.oc1.iad.035a1179475688eb20aab17d4701eea4a55cf82093126679d683e58c9db81140"
  }
}
override_resource {
  target          = oci_vault_secret.presenter
  override_during = plan
  values          = { id = "ocid1.vaultsecret.oc1.iad.680d29a4cf328610a930720884591bbb4a9e07d6b5f284d96a01230de85582fe" }
}
override_resource {
  target          = oci_vault_secret.provider["anthropic"]
  override_during = plan
  values          = { id = "ocid1.vaultsecret.oc1.iad.9608ac59223d56beff9a76025888519a7bff3c8a10914bf5c2a4d50276893a1a" }
}
override_resource {
  target          = oci_vault_secret.provider["openai"]
  override_during = plan
  values          = { id = "ocid1.vaultsecret.oc1.iad.0d925bf884657de344752a2e6160775d99a3cb645e981bf2c30704459e9bc313" }
}
variables {
  tenancy_ocid        = "ocid1.tenancy.oc1..586a2f31b730c96d0ec94a8665fa12007b60c00941530af69d871e4c933f2701"
  compartment_ocid    = "ocid1.compartment.oc1..139c70ae8659d8823bca678f44776a094f00dd911220ef906b778b6c102958f5"
  region              = "us-ashburn-1"
  deployment_id       = "gateway-console-metadata-budget-test-123"
  image_ocid          = "ocid1.image.oc1.iad.547931db41e65022a8a0ff1c78707689e32184967b0e309855a41d4b02b69013"
  availability_domain = "synthetic:US-ASHBURN-AD-1"
  enable_oci          = true
  enable_anthropic    = true
  enable_openai       = true
  oci_model_id        = "oci.${sha256("oci-model-1")}.${sha256("oci-model-2")}.${sha256("oci-model-3")}.${substr(sha256("oci-model-4"), 0, 56)}"
  anthropic_model_id  = "anthropic.${sha256("anthropic-model-1")}.${sha256("anthropic-model-2")}.${sha256("anthropic-model-3")}.${substr(sha256("anthropic-model-4"), 0, 50)}"
  openai_model_id     = "openai.${sha256("openai-model-1")}.${sha256("openai-model-2")}.${sha256("openai-model-3")}.${substr(sha256("openai-model-4"), 0, 53)}"
  presenter_email     = "presenter-for-a-reusable-customer-gateway-demonstration@example.invalid"
}
run "all_providers_fit_metadata_with_real_source_hashes" {
  command = plan
  assert {
    condition     = length(base64gzip(local.cloud_init)) < 16000
    error_message = "All-provider bootstrap exceeds metadata budget: ${length(base64gzip(local.cloud_init))} characters."
  }
  assert {
    condition     = jsondecode(yamldecode(local.cloud_init).write_files[0].content) == { for name in local.embedded_assets : name => file("${local.asset_root}/${name}") }
    error_message = "The plain asset map must preserve every embedded file byte."
  }
  assert {
    condition     = yamldecode(local.cloud_init).write_files[1].content == file("${local.asset_root}/runtime/install_assets.py") && alltrue([for item in yamldecode(local.cloud_init).write_files : item.owner == "root:root" && item.permissions == "0600" && !can(item.encoding)])
    error_message = "Bootstrap files must preserve installer bytes, ownership and private permissions."
  }
  assert {
    condition = yamldecode(local.cloud_init).runcmd == [
      ["/usr/bin/python3", "/opt/oci-ai-gateway/install_assets.py"],
      ["/usr/bin/systemctl", "daemon-reload"],
      ["/usr/bin/systemctl", "enable", "--now", "oci-ai-gateway-bootstrap.timer"],
    ]
    error_message = "Assets must be installed before enabling the unchanged bootstrap timer."
  }
}

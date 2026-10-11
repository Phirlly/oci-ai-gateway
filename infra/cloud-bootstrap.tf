locals {
  oci_inference_enabled = var.schema_version != 4 || contains(keys(var.models), "oci")
  native_model_id       = var.schema_version == 4 ? lookup(var.models, "oci", null) : var.oci_model_id
  runtime_assets = [
    "runtime/__init__.py", "runtime/bootstrap.py", "runtime/cloud_credentials.py",
    "runtime/gateway_entrypoint.py", "runtime/gateway_http.py", "runtime/host_commands.py",
    "runtime/host_firewall.py", "runtime/password_policy.py", "runtime/presenter.py",
    "runtime/presenter_api.py", "runtime/presenter_state.py", "runtime/runtime_bundle.py",
    "runtime/runtime_files.py", "runtime/compose.cloud.yaml", "runtime/docker-daemon.json",
    "runtime/systemd/docker-guard.conf", "runtime/systemd/oci-ai-gateway-bootstrap.service",
    "runtime/systemd/oci-ai-gateway-bootstrap.timer",
  ]
  runtime_settings = merge({
    schema_version                        = var.schema_version >= 3 ? var.schema_version : 1
    deployment_id                         = var.deployment_id
    tenancy_ocid                          = var.tenancy_ocid
    compartment_ocid                      = var.compartment_ocid
    secret_ocid                           = oci_vault_secret.runtime.id
    region                                = var.region
    presenter_email                       = var.presenter_email
    }, var.schema_version == 4 ? { models = var.models } : {}, var.schema_version == 4 ? {} : {
    model_id                              = var.oci_model_id
    external_provider                     = var.external_provider
    external_model_id                     = var.external_model_id
  }, local.oci_inference_enabled ? { inference_region = var.inference_region } : {})
  native_bootstrap_assets = [
    "runtime/__init__.py", "runtime/install_assets.py", "runtime/gateway_http.py",
    "runtime/source_archive.py", "runtime/source_download.py", "runtime/source_bootstrap.py",
    "runtime/systemd/oci-ai-gateway-native-bootstrap.service",
    "runtime/systemd/oci-ai-gateway-bootstrap.timer",
  ]
  native_source = fileexists("${path.module}/../runtime/source.json") ? file("${path.module}/../runtime/source.json") : ""
  cloud_init = "#cloud-config\n${yamlencode({
    write_files = concat([
      {
        path        = "/opt/oci-ai-gateway/assets.json"
        owner       = "root:root"
        permissions = "0600"
        encoding    = "gz+b64"
        content     = base64gzip(jsonencode({ for name in(var.schema_version >= 3 ? local.native_bootstrap_assets : local.runtime_assets) : name => file("${path.module}/../${name}") }))
      },
      {
        path        = "/opt/oci-ai-gateway/install_assets.py"
        owner       = "root:root"
        permissions = "0600"
        encoding    = "gz+b64"
        content     = base64gzip(file("${path.module}/../runtime/install_assets.py"))
      },
      {
        path        = "/etc/oci-ai-gateway.json"
        owner       = "root:root"
        permissions = "0600"
        content     = jsonencode(local.runtime_settings)
      },
      ], var.schema_version >= 3 ? [{
        path        = "/etc/oci-ai-gateway-source.json"
        owner       = "root:root"
        permissions = "0600"
        content     = local.native_source
    }] : [])
    runcmd = [
      "set -eu",
      ["/usr/bin/python3", "/opt/oci-ai-gateway/install_assets.py"],
      ["/usr/bin/systemctl", "daemon-reload"],
      ["/usr/bin/systemctl", "enable", "--now", "oci-ai-gateway-bootstrap.timer"],
    ]
  })}"
}

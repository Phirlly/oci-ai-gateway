locals {
  source_manifest = file("${path.module}/source.json")
  asset_root      = fileexists("${path.module}/runtime/install_assets.py") ? path.module : "${path.module}/.."
  embedded_assets = [
    "runtime/__init__.py", "runtime/install_assets.py", "runtime/gateway_http.py",
    "runtime/source_archive.py", "runtime/source_download.py", "runtime/source_bootstrap.py",
    "runtime/systemd/oci-ai-gateway-console-bootstrap.service",
    "runtime/systemd/oci-ai-gateway-bootstrap.timer",
  ]
  cloud_init = "#cloud-config\n${yamlencode({
    write_files = [
      {
        path        = "/opt/oci-ai-gateway/assets.json"
        owner       = "root:root"
        permissions = "0600"
        encoding    = "gz+b64"
        content     = base64gzip(jsonencode({ for name in local.embedded_assets : name => file("${local.asset_root}/${name}") }))
      },
      {
        path        = "/opt/oci-ai-gateway/install_assets.py"
        owner       = "root:root"
        permissions = "0600"
        encoding    = "gz+b64"
        content     = base64gzip(file("${local.asset_root}/runtime/install_assets.py"))
      },
      {
        path        = "/etc/oci-ai-gateway.json"
        owner       = "root:root"
        permissions = "0600"
        content     = jsonencode(local.runtime_settings)
      },
      {
        path        = "/etc/oci-ai-gateway-console.json"
        owner       = "root:root"
        permissions = "0600"
        content     = jsonencode(local.console_settings)
      },
      {
        path        = "/etc/oci-ai-gateway-source.json"
        owner       = "root:root"
        permissions = "0600"
        content     = local.source_manifest
      },
    ]
    runcmd = [
      ["/usr/bin/python3", "/opt/oci-ai-gateway/install_assets.py"],
      ["/usr/bin/systemctl", "daemon-reload"],
      ["/usr/bin/systemctl", "enable", "--now", "oci-ai-gateway-bootstrap.timer"],
    ]
  })}"
}

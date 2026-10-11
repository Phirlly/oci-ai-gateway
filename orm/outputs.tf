output "status_url" {
  description = "Last verification result. Apply success alone does not mean Ready."
  value       = "https://${module.gateway.public_ip}/deployment-status"
}
output "compare_url" {
  description = "Open after status reports Ready."
  value       = "https://${module.gateway.public_ip}/ui/playground/?tab=compare"
}
output "presenter_username" {
  value = var.presenter_email
}
output "external_key_secret_url" {
  description = "Create a CURRENT plain-text version containing the Anthropic API key."
  value       = "https://cloud.oracle.com/security/secrets/${module.gateway.runtime_secret_ocid}?region=${var.region}"
}
output "presenter_password_secret_url" {
  description = "View secret contents and copy the password field; never put it in Terraform."
  value       = "https://cloud.oracle.com/security/secrets/${oci_vault_secret.presenter.id}?region=${var.region}"
}

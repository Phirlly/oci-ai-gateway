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
output "anthropic_key_secret_url" {
  description = "Only when Anthropic is enabled: save its API key as a CURRENT plain-text secret version."
  value       = var.enable_anthropic ? "https://cloud.oracle.com/security/secrets/${oci_vault_secret.provider["anthropic"].id}?region=${var.region}" : null
}
output "openai_key_secret_url" {
  description = "Only when OpenAI is enabled: save its API key as a CURRENT plain-text secret version."
  value       = var.enable_openai ? "https://cloud.oracle.com/security/secrets/${oci_vault_secret.provider["openai"].id}?region=${var.region}" : null
}
output "enabled_models" {
  description = "Only these configured models are available to the presenter and verification."
  value       = local.models
}
output "presenter_password_secret_url" {
  description = "View secret contents and copy the password field; never put it in Terraform."
  value       = "https://cloud.oracle.com/security/secrets/${oci_vault_secret.presenter.id}?region=${var.region}"
}

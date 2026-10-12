variable "tenancy_ocid" {
  type        = string
  description = "Automatically populated by Resource Manager."
}
variable "compartment_ocid" {
  type        = string
  description = "Compartment for all deployment-owned resources."
}
variable "region" {
  type        = string
  description = "Subscribed OC1 hosting region."
}
variable "deployment_id" {
  type        = string
  description = "Unique name for this independent deployment; retain it for its lifetime."
  default     = "ai-gateway"
}
variable "availability_domain" {
  type        = string
  description = "Hosting availability domain."
}
variable "image_ocid" {
  type        = string
  description = "Regional Ubuntu24.04 AMD image. Retain the selected OCID on subsequent Applies."
}
variable "oci_model_id" {
  type        = string
  description = "Native OCI Chat model available to this tenancy in the inference region."
  default     = "google.gemini-2.5-flash-lite"
}
variable "inference_region" {
  type        = string
  description = "Optional subscribed inference region; blank uses the hosting region."
  default     = null
}
variable "enable_oci" {
  type        = bool
  default     = true
  nullable    = false
  description = "Enable the OCI Generative AI route. At least one provider must be enabled."
}
variable "enable_anthropic" {
  type        = bool
  default     = false
  nullable    = false
  description = "Optional Anthropic route; select a saved secret or supply its API key after Apply."
}
variable "enable_openai" {
  type        = bool
  default     = false
  nullable    = false
  description = "Optional OpenAI route; select a saved secret or supply its API key after Apply."
}
variable "anthropic_model_id" {
  type        = string
  description = "Anthropic model accessible with the supplied provider key."
  default     = "claude-sonnet-4-6"
}
variable "openai_model_id" {
  type        = string
  description = "OpenAI Chat Completions model accessible with your project API key."
  default     = "gpt-4.1-mini-2025-04-14"
}
variable "presenter_email" {
  type        = string
  description = "Presenter username; no email is sent."
  default     = "presenter@example.com"
}
variable "instance_shape" {
  type        = string
  description = "Supported AMD CPU shape."
  default     = "VM.Standard.E5.Flex"
}
variable "instance_ocpus" {
  type        = number
  default     = 2
  description = "VM OCPUs."
}
variable "instance_memory_gbs" {
  type        = number
  default     = 16
  description = "VM memory in GB."
}
variable "verification_run" {
  type        = number
  default     = 1
  nullable    = false
  description = "Increase to retry samples or refresh a corrected external key. Never decrease."
  validation {
    condition     = var.verification_run >= 1 && var.verification_run <= 20 && floor(var.verification_run) == var.verification_run
    error_message = "verification_run must be an integer from1 to20."
  }
}

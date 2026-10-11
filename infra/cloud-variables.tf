variable "console_image_ocid" {
  description = "Optional retained regional image selected by the Console root."
  type        = string
  default     = null
  validation {
    condition     = var.console_image_ocid == null ? true : can(regex("^ocid1\\.image\\.oc1\\.[a-z0-9-]+\\.[a-zA-Z0-9._-]+$", var.console_image_ocid))
    error_message = "Console image must be an OC1 image OCID."
  }
}

variable "console_ad_name" {
  description = "Optional named availability domain selected by the Console root."
  type        = string
  default     = null
}

variable "console_cloud_init" {
  description = "Optional nonsecret Console bootstrap; never include credentials."
  type        = string
  default     = null
}

variable "console_mode" {
  description = "Console root owns individual credential secrets instead of the controller bundle."
  type        = bool
  default     = false
  nullable    = false
}

variable "schema_version" {
  description = "Version4 optional providers; versions2/3 retained for original package recovery."
  type        = number
  nullable    = false
  validation {
    condition     = contains([2, 3, 4], var.schema_version)
    error_message = "Invalid schema_version; use version4 for optional providers."
  }
}

variable "inference_region" {
  description = "Subscribed OC1 region serving the selected OCI-managed model."
  type        = string
  default     = null
  validation {
    condition     = var.inference_region == null ? true : can(regex("^[a-z]{2,}-[a-z0-9-]+-[0-9]+$", var.inference_region))
    error_message = "Invalid inference_region; use the supported version2 deployment settings."
  }
}

variable "external_provider" {
  description = "Supported external adapter for this demo."
  type        = string
  default     = null
  validation {
    condition     = var.external_provider == null || var.external_provider == "anthropic"
    error_message = "Invalid external_provider; use the supported version2 deployment settings."
  }
}

variable "external_model_id" {
  description = "Exact external model identifier."
  type        = string
  default     = null
  validation {
    condition     = var.external_model_id == null ? true : can(regex("^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$", var.external_model_id))
    error_message = "Invalid external_model_id; use the supported version2 deployment settings."
  }
}

variable "models" {
  description = "Schema4 only: omit a provider to disable it; one model ID per enabled provider."
  type        = map(string)
  default     = {}
  nullable    = false
  validation {
    condition     = alltrue([for provider, model in var.models : contains(["oci", "anthropic", "openai"], provider) && can(regex("^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,254}$", model))])
    error_message = "models accepts only oci, anthropic and openai with nonempty model IDs."
  }
}

variable "presenter_email" {
  description = "Presenter login name; no invitation email is sent."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[a-zA-Z0-9._+%-]{1,64}@[a-zA-Z0-9-]+(\\.[a-zA-Z0-9-]+)+$", var.presenter_email))
    error_message = "Invalid presenter_email; use the supported version2 deployment settings."
  }
}

variable "instance_shape" {
  description = "Supported AMD CPU shape; no GPU is required."
  type        = string
  nullable    = false
  validation {
    condition     = contains(["VM.Standard.E4.Flex", "VM.Standard.E5.Flex"], var.instance_shape)
    error_message = "Invalid instance_shape; use the supported version2 deployment settings."
  }
}

variable "instance_ocpus" {
  description = "OCPUs assigned to the gateway VM."
  type        = number
  nullable    = false
  validation {
    condition     = var.instance_ocpus >= 1 && var.instance_ocpus <= 16 && floor(var.instance_ocpus) == var.instance_ocpus
    error_message = "Invalid instance_ocpus; use the supported version2 deployment settings."
  }
}

variable "instance_memory_gbs" {
  description = "VM memory in GB; also constrained to the selected OCPUs."
  type        = number
  nullable    = false
  validation {
    condition     = var.instance_memory_gbs >= 8 && var.instance_memory_gbs <= 256 && floor(var.instance_memory_gbs) == var.instance_memory_gbs
    error_message = "Invalid instance_memory_gbs; use the supported version2 deployment settings."
  }
}

variable "boot_volume_size_gbs" {
  description = "Owned boot disk capacity in GB."
  type        = number
  nullable    = false
  validation {
    condition     = var.boot_volume_size_gbs >= 50 && var.boot_volume_size_gbs <= 500 && floor(var.boot_volume_size_gbs) == var.boot_volume_size_gbs
    error_message = "Invalid boot_volume_size_gbs; use the supported version2 deployment settings."
  }
}

variable "availability_domain_number" {
  description = "One-based availability domain selection within the hosting region."
  type        = number
  nullable    = false
  validation {
    condition     = contains([1, 2, 3], var.availability_domain_number)
    error_message = "Invalid availability_domain_number; use the supported version2 deployment settings."
  }
}

variable "image_name" {
  description = "Exact published Ubuntu24.04 image build; no latest-image fallback."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^Canonical-Ubuntu-24\\.04-[0-9]{4}\\.[0-9]{2}\\.[0-9]{2}-[0-9]+$", var.image_name))
    error_message = "Invalid image_name; use the supported version2 deployment settings."
  }
}

variable "model_key_ttl_days" {
  description = "Legacy-only model key validity; native settings omit this value."
  type        = number
  default     = null
  validation {
    condition     = var.model_key_ttl_days == null ? true : (var.model_key_ttl_days >= 1 && var.model_key_ttl_days <= 30 && floor(var.model_key_ttl_days) == var.model_key_ttl_days)
    error_message = "Invalid model_key_ttl_days; use the supported version2 deployment settings."
  }
}

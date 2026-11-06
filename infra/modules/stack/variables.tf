variable "environment" {
  description = "Ambiente: local, dev o prod."
  type        = string

  validation {
    condition     = contains(["local", "dev", "prod"], var.environment)
    error_message = "El ambiente debe ser local, dev o prod."
  }
}

variable "location" {
  description = "Region permitida por la politica de tu suscripcion (ver scripts/check-regions.sh)."
  type        = string
}

variable "database_location" {
  description = "Region de Azure SQL, si debe ser otra: SQL restringe regiones por suscripcion. Con null usa location."
  type        = string
  default     = null
}

variable "image" {
  description = "Imagen fijada por digest, para que prod ejecute exactamente lo probado en dev."
  type        = string

  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.image))
    error_message = "La imagen debe fijarse por digest: registro/imagen@sha256:..."
  }
}

variable "max_replicas" {
  description = "Tope de replicas."
  type        = number
  default     = 1

  validation {
    condition     = var.max_replicas >= 1 && var.max_replicas <= 3
    error_message = "max_replicas debe estar entre 1 y 3 para proteger el credito."
  }
}

variable "jwt_minutes" {
  description = "Vigencia de los tokens."
  type        = number
  default     = 30
}

variable "use_free_offer" {
  description = "Usa la oferta gratuita de Azure SQL."
  type        = bool
  default     = true
}

variable "rbac_propagation_wait" {
  description = "Espera tras cada asignacion de rol."
  type        = string
  default     = "90s"
}

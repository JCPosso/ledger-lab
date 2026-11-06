variable "server_name" {
  description = "Nombre global del servidor logico."
  type        = string
}

variable "database_name" {
  description = "Nombre de la base de datos."
  type        = string
  default     = "ledger"
}

variable "resource_group_name" {
  description = "Grupo de recursos."
  type        = string
}

variable "location" {
  description = "Region de Azure."
  type        = string
}

variable "admin_login" {
  description = "Usuario administrador SQL."
  type        = string
  default     = "ledgeradmin"
}

variable "use_free_offer" {
  description = "Usa la oferta gratuita de Azure SQL. Con false, cada hora de computo se cobra."
  type        = bool
  default     = true
}

variable "auto_pause_delay_minutes" {
  description = "Minutos antes de pausar, sin oferta gratuita. Con ella Azure fija su propio valor. El minimo es 15."
  type        = number
  default     = 15

  validation {
    condition     = var.auto_pause_delay_minutes >= 15
    error_message = "La pausa automatica requiere al menos 15 minutos."
  }
}

variable "max_size_gb" {
  description = "Tamano maximo sin oferta gratuita. Con ella Azure fija el tamano por defecto (32 GB)."
  type        = number
  default     = 2

  validation {
    condition     = var.max_size_gb >= 1 && var.max_size_gb <= 32
    error_message = "El tamano debe estar entre 1 y 32 GB."
  }
}

variable "tags" {
  description = "Etiquetas."
  type        = map(string)
  default     = {}
}

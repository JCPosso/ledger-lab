variable "name" {
  description = "Nombre global del Key Vault."
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]$", var.name))
    error_message = "El nombre debe tener de 3 a 24 caracteres, iniciar con letra y no terminar en guion."
  }
}

variable "resource_group_name" {
  description = "Grupo de recursos."
  type        = string
}

variable "location" {
  description = "Region de Azure."
  type        = string
}

variable "purge_protection_enabled" {
  description = "Impide purgar el vault durante la retencion. Es irreversible una vez activado."
  type        = bool
}

variable "secrets" {
  description = "Secretos a guardar, por nombre."
  type        = map(string)
  sensitive   = true
}

variable "rbac_propagation_wait" {
  description = "Espera tras asignar el rol de escritura."
  type        = string
  default     = "90s"
}

variable "tags" {
  description = "Etiquetas."
  type        = map(string)
  default     = {}
}

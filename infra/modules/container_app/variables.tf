variable "name" {
  description = "Sufijo comun de los recursos."
  type        = string
}

variable "resource_group_name" {
  description = "Grupo de recursos."
  type        = string
}

variable "location" {
  description = "Region de Azure."
  type        = string
}

variable "image" {
  description = "Imagen del contenedor."
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault del que la app lee secretos."
  type        = string
}

variable "secret_ids" {
  description = "Debe incluir database-url y jwt-secret."
  type        = map(string)

  validation {
    condition     = alltrue([for name in ["database-url", "jwt-secret"] : contains(keys(var.secret_ids), name)])
    error_message = "secret_ids debe incluir database-url y jwt-secret."
  }
}

variable "environment_variables" {
  description = "Variables de entorno no secretas."
  type        = map(string)
  default     = {}
}

variable "min_replicas" {
  description = "Con 0 la app escala a cero y no consume computo sin trafico."
  type        = number
  default     = 0
}

variable "max_replicas" {
  description = "Tope de replicas; limita tambien el costo maximo."
  type        = number
  default     = 1
}

variable "logs_enabled" {
  description = "Crea un workspace de Log Analytics con tope diario."
  type        = bool
  default     = false
}

variable "rbac_propagation_wait" {
  description = "Espera tras asignar el rol de lectura."
  type        = string
  default     = "90s"
}

variable "tags" {
  description = "Etiquetas."
  type        = map(string)
  default     = {}
}

terraform {
  required_version = ">= 1.11"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.0"
    }
  }

  # La cuenta y la clave se pasan con -backend-config; ver .github/workflows/deploy-env.yml.
  backend "azurerm" {
    use_azuread_auth = true
  }
}

# En GitHub Actions la identidad llega por OIDC (ARM_USE_OIDC y ARM_CLIENT_ID); en tu equipo, de `az login`.
provider "azurerm" {
  storage_use_azuread             = true
  resource_provider_registrations = "none"

  features {
    key_vault {
      purge_soft_delete_on_destroy = false
    }
  }
}

provider "azapi" {}

variable "location" {
  type = string
}

variable "database_location" {
  type    = string
  default = null
}

variable "image" {
  type = string
}

variable "use_free_offer" {
  type    = bool
  default = true
}

module "stack" {
  source = "../../modules/stack"

  environment       = "prod"
  location          = var.location
  database_location = var.database_location
  image             = var.image
  use_free_offer    = var.use_free_offer
  max_replicas      = 3
  jwt_minutes       = 15
}

output "app_url" {
  value = module.stack.app_url
}

output "resource_group_name" {
  value = module.stack.resource_group_name
}

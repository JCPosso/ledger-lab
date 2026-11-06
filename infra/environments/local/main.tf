# Ambiente contra floci-az: mismo modulo, sin cuenta de Azure. Ver docs/floci.md.

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
}

# floci-az no valida credenciales: estos identificadores son ficticios a proposito.
provider "azurerm" {
  use_cli                         = false
  environment                     = "stack"
  metadata_host                   = "localhost:4577"
  subscription_id                 = "00000000-0000-0000-0000-000000000001"
  tenant_id                       = "00000000-0000-0000-0000-000000000002"
  client_id                       = "00000000-0000-0000-0000-000000000003"
  client_secret                   = "floci-no-valida-esto"
  resource_provider_registrations = "none"

  features {}
}

# Requerido por el modulo, pero aqui no crea nada: use_free_offer es false.
provider "azapi" {
  use_cli         = false
  subscription_id = "00000000-0000-0000-0000-000000000001"
  tenant_id       = "00000000-0000-0000-0000-000000000002"
  client_id       = "00000000-0000-0000-0000-000000000003"
  client_secret   = "floci-no-valida-esto"
}

variable "image" {
  type    = string
  default = "ghcr.io/example/ledger@sha256:0000000000000000000000000000000000000000000000000000000000000000"
}

module "stack" {
  source = "../../modules/stack"

  environment           = "local"
  location              = "eastus"
  image                 = var.image
  use_free_offer        = false
  rbac_propagation_wait = "1s"
}

output "app_url" {
  value = module.stack.app_url
}

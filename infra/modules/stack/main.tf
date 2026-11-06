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
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }
}

locals {
  name = "ledger-${var.environment}"
  tags = {
    project     = "eci-ledger-lab"
    environment = var.environment
    managed_by  = "terraform"
  }
  # Solo prod queda protegido contra purgas y con logs: dev debe poder borrarse sin residuos.
  is_prod = var.environment == "prod"
}

# Los nombres de Key Vault y SQL son globales en todo Azure.
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "random_password" "jwt" {
  length  = 64
  special = false
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

module "database" {
  source = "../database"

  server_name         = "sql-${local.name}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.this.name
  location            = coalesce(var.database_location, azurerm_resource_group.this.location)
  use_free_offer      = var.use_free_offer
  tags                = local.tags
}

module "key_vault" {
  source = "../key_vault"

  name                     = "kv-${var.environment}-${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  purge_protection_enabled = local.is_prod
  rbac_propagation_wait    = var.rbac_propagation_wait
  tags                     = local.tags

  secrets = {
    "database-url" = module.database.database_url
    "jwt-secret"   = random_password.jwt.result
  }
}

module "app" {
  source = "../container_app"

  name                  = local.name
  resource_group_name   = azurerm_resource_group.this.name
  location              = azurerm_resource_group.this.location
  image                 = var.image
  key_vault_id          = module.key_vault.id
  secret_ids            = module.key_vault.secret_ids
  max_replicas          = var.max_replicas
  logs_enabled          = local.is_prod
  rbac_propagation_wait = var.rbac_propagation_wait
  tags                  = local.tags

  environment_variables = {
    APP_ENV     = var.environment
    JWT_MINUTES = tostring(var.jwt_minutes)
  }
}

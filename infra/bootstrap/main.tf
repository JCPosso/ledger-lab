# Se ejecuta una sola vez desde tu equipo, con `az login`. Crea lo que GitHub Actions necesita antes de
# poder desplegar: el estado remoto de dev y prod, y una identidad administrada que entra con OIDC.
# Su propio estado queda local.

terraform {
  required_version = ">= 1.11"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
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

provider "azurerm" {
  use_cli                         = true
  storage_use_azuread             = true
  resource_provider_registrations = "none"
  features {}
}

variable "location" {
  description = "Region permitida por la politica de tu suscripcion."
  type        = string
}

variable "github_repository" {
  description = "Repositorio que puede desplegar, como usuario/repositorio."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.github_repository))
    error_message = "Usa el formato usuario/repositorio."
  }
}

variable "github_subject_repo" {
  description = "Repositorio como lo escribe GitHub en el token: usuario@id/repositorio@id. Si queda vacío se usa github_repository."
  type        = string
  default     = ""
}

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "azurerm_resource_group" "state" {
  name     = "rg-ledger-tfstate"
  location = var.location
  tags     = { project = "eci-ledger-lab", managed_by = "terraform" }
}

resource "azurerm_storage_account" "state" {
  #checkov:skip=CKV_AZURE_33:No se usa el servicio de colas en esta cuenta
  #checkov:skip=CKV_AZURE_59:Terraform corre desde tu equipo; el acceso exige Entra ID y claves desactivadas
  #checkov:skip=CKV_AZURE_206:LRS basta: el estado se versiona y puede reconstruirse en un laboratorio
  #checkov:skip=CKV2_AZURE_33:Un private endpoint cuesta cerca de 7 USD al mes y exige una VNet
  #checkov:skip=CKV2_AZURE_1:La llave administrada por Microsoft basta; CMK exige mas infraestructura
  name                            = "stledger${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.state.name
  location                        = azurerm_resource_group.state.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false # Solo Entra ID: el estado contiene secretos.
  default_to_oauth_authentication = true
  tags                            = azurerm_resource_group.state.tags

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
  }
}

resource "azurerm_role_assignment" "state_owner" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "time_sleep" "rbac_propagation" {
  depends_on      = [azurerm_role_assignment.state_owner]
  create_duration = "90s"
}

resource "azurerm_storage_container" "state" {
  #checkov:skip=CKV2_AZURE_21:Los logs de diagnostico del blob se cobran; el acceso ya exige Entra ID
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
  depends_on            = [time_sleep.rbac_propagation]
}

# Identidad de GitHub Actions. No es un service principal con secreto: no hay contrasena que guardar.
resource "azurerm_user_assigned_identity" "github" {
  name                = "id-ledger-github"
  resource_group_name = azurerm_resource_group.state.name
  location            = azurerm_resource_group.state.location
  tags                = azurerm_resource_group.state.tags
}

# Azure solo acepta tokens de este repositorio y de estos dos GitHub Environments.
resource "azurerm_federated_identity_credential" "github" {
  for_each = toset(["dev", "prod"])

  name                      = "github-${each.key}"
  user_assigned_identity_id = azurerm_user_assigned_identity.github.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:${local.subject_repo}:environment:${each.key}"
}

locals {
  subscription_scope = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"

  # Key Vault Secrets Officer y Key Vault Secrets User: los unicos roles que el pipeline puede asignar.
  assignable_roles = "b86a8fe4-44ce-4948-aee5-eccb2c155cd7, 4633458b-17de-408a-b874-0445c86b69e6"
  subject_repo     = var.github_subject_repo != "" ? var.github_subject_repo : var.github_repository
}

# Terraform crea grupos de recursos, asi que el alcance debe ser la suscripcion.
resource "azurerm_role_assignment" "github_contributor" {
  scope                = local.subscription_scope
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
  principal_type       = "ServicePrincipal"
}

# Contributor no puede asignar roles. Este permiso lo habilita, limitado por la condicion a los
# dos roles de Key Vault: el pipeline no puede otorgarse Owner a si mismo.
resource "azurerm_role_assignment" "github_rbac_admin" {
  scope                = local.subscription_scope
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
  principal_type       = "ServicePrincipal"
  condition_version    = "2.0"
  condition            = <<-EOT
    (
      (!(ActionMatches{'Microsoft.Authorization/roleAssignments/write'}))
      OR
      (@Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${local.assignable_roles}})
    )
    AND
    (
      (!(ActionMatches{'Microsoft.Authorization/roleAssignments/delete'}))
      OR
      (@Resource[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${local.assignable_roles}})
    )
  EOT
}

resource "azurerm_role_assignment" "github_state" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
  principal_type       = "ServicePrincipal"
}

output "azure_client_id" {
  description = "Identifica la identidad. No es un secreto."
  value       = azurerm_user_assigned_identity.github.client_id
}

output "azure_tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "azure_subscription_id" {
  value = data.azurerm_client_config.current.subscription_id
}

output "resource_group_name" {
  value = azurerm_resource_group.state.name
}

output "storage_account_name" {
  value = azurerm_storage_account.state.name
}

output "container_name" {
  value = azurerm_storage_container.state.name
}

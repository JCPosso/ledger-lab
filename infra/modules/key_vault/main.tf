terraform {
  required_version = ">= 1.11"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }
}

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "this" {
  #checkov:skip=CKV_AZURE_189:Terraform corre desde tu equipo y sin VNet no hay ruta privada; protege RBAC
  #checkov:skip=CKV_AZURE_109:Un firewall bloquearia a Container Apps, cuya IP de salida no es fija
  #checkov:skip=CKV2_AZURE_32:Un private endpoint cuesta cerca de 7 USD al mes por recurso
  name                       = var.name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  purge_protection_enabled   = var.purge_protection_enabled
  tags                       = var.tags
}

# La persona que ejecuta Terraform (az login) escribe los secretos. No hay service principal.
resource "azurerm_role_assignment" "deployer" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Los roles de Azure tardan en propagarse; sin esta espera la escritura devuelve 403.
resource "time_sleep" "rbac_propagation" {
  depends_on      = [azurerm_role_assignment.deployer]
  create_duration = var.rbac_propagation_wait
}

resource "azurerm_key_vault_secret" "this" {
  #checkov:skip=CKV_AZURE_41:Un secreto vencido tumbaria la app sin un proceso de rotacion, fuera de alcance
  for_each = nonsensitive(toset(keys(var.secrets)))

  name         = each.key
  value        = var.secrets[each.key]
  key_vault_id = azurerm_key_vault.this.id
  content_type = "text/plain"
  depends_on   = [time_sleep.rbac_propagation]
}

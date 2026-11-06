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
  }
}

locals {
  serverless_sku = "GP_S_Gen5_2"
  database_id    = var.use_free_offer ? azapi_resource.free[0].id : azurerm_mssql_database.paid[0].id
}

resource "random_password" "admin" {
  length           = 32
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  special          = false
  override_special = ""
}

resource "azurerm_mssql_server" "this" {
  #checkov:skip=CKV_AZURE_113:Sin VNet de pago la app llega por red publica; el firewall y TLS la limitan
  #checkov:skip=CKV2_AZURE_45:Un private endpoint cuesta cerca de 7 USD al mes por recurso
  #checkov:skip=CKV2_AZURE_27:La app usa login SQL con secreto en Key Vault; Entra queda como extension
  #checkov:skip=CKV2_AZURE_2:Vulnerability Assessment requiere Defender for SQL, que tiene costo
  #checkov:skip=CKV_AZURE_23:La auditoria requiere un destino de almacenamiento con costo; extension opcional
  #checkov:skip=CKV_AZURE_24:Depende de la auditoria, que no se habilita en este laboratorio
  name                          = var.server_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  version                       = "12.0"
  administrator_login           = var.admin_login
  administrator_login_password  = random_password.admin.result
  minimum_tls_version           = "1.2"
  public_network_access_enabled = true
  tags                          = var.tags
}

# Sin VNet ni private endpoint (tienen costo) Container Apps sale por IP publicas variables.
# 0.0.0.0 es la regla especial "permitir servicios de Azure"; es la concesion de este laboratorio.
resource "azurerm_mssql_firewall_rule" "azure_services" {
  #checkov:skip=CKV2_AZURE_34:Es la regla de servicios de Azure; las IP de salida de la app no son fijas
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# azurerm no expone useFreeLimit, por eso la oferta gratuita se crea con azapi.
resource "azapi_resource" "free" {
  count = var.use_free_offer ? 1 : 0

  type      = "Microsoft.Sql/servers/databases@2023-08-01"
  name      = var.database_name
  parent_id = azurerm_mssql_server.this.id
  location  = var.location
  tags      = var.tags

  body = {
    sku = {
      # Azure devuelve el nombre sin la capacidad; con GP_S_Gen5_2 cada plan mostraria un cambio.
      name     = "GP_S_Gen5"
      tier     = "GeneralPurpose"
      family   = "Gen5"
      capacity = 2
    }
    # La oferta gratuita con AutoPause rechaza tamano y pausa propios: solo se declara lo que documenta.
    properties = {
      useFreeLimit                = true
      freeLimitExhaustionBehavior = "AutoPause"
    }
  }
}

resource "azurerm_mssql_database" "paid" {
  #checkov:skip=CKV_AZURE_224:Las tablas de la app ya llevan partida doble; Ledger de SQL no es requisito aqui
  #checkov:skip=CKV_AZURE_229:La redundancia de zona duplica el costo de computo
  count = var.use_free_offer ? 0 : 1

  name                        = var.database_name
  server_id                   = azurerm_mssql_server.this.id
  sku_name                    = local.serverless_sku
  min_capacity                = 0.5
  auto_pause_delay_in_minutes = var.auto_pause_delay_minutes
  max_size_gb                 = var.max_size_gb
  storage_account_type        = "Local"
  tags                        = var.tags
}

# Pruebas sin nube: mock_provider no necesita credenciales, ni SPN, ni emulador.

mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000001"
      object_id = "00000000-0000-0000-0000-000000000002"
    }
  }
  mock_resource "azurerm_key_vault" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv"
    }
  }
  mock_resource "azurerm_key_vault_secret" {
    defaults = {
      versionless_id = "https://kv.vault.azure.net/secrets/secreto"
    }
  }
  mock_resource "azurerm_mssql_server" {
    defaults = {
      id                          = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Sql/servers/sql"
      fully_qualified_domain_name = "sql.database.windows.net"
    }
  }
  mock_resource "azurerm_user_assigned_identity" {
    defaults = {
      id           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id"
      principal_id = "00000000-0000-0000-0000-000000000003"
    }
  }
  mock_resource "azurerm_container_app_environment" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.App/managedEnvironments/cae"
    }
  }
  mock_resource "azurerm_log_analytics_workspace" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/log"
    }
  }
  mock_resource "azurerm_container_app" {
    defaults = {
      ingress = { fqdn = "ledger.azurecontainerapps.io" }
    }
  }
}

mock_provider "azapi" {}
mock_provider "random" {}
mock_provider "time" {}

variables {
  location              = "eastus"
  image                 = "ghcr.io/eci/ledger@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  rbac_propagation_wait = "1s"
}

run "dev_es_desechable_y_sin_logs" {
  command = apply

  variables {
    environment = "dev"
  }

  assert {
    condition     = azurerm_resource_group.this.name == "rg-ledger-dev"
    error_message = "El grupo de recursos debe incluir el ambiente."
  }
  assert {
    condition     = azurerm_resource_group.this.tags["environment"] == "dev"
    error_message = "Las etiquetas deben identificar el ambiente."
  }
  assert {
    condition     = startswith(output.app_url, "https://")
    error_message = "La URL publica debe ser HTTPS."
  }
  assert {
    condition     = local.is_prod == false
    error_message = "dev no debe activar la configuracion de prod."
  }
}

run "prod_se_protege" {
  command = apply

  variables {
    environment  = "prod"
    max_replicas = 3
  }

  assert {
    condition     = azurerm_resource_group.this.name == "rg-ledger-prod"
    error_message = "El grupo de recursos debe incluir el ambiente."
  }
  assert {
    condition     = local.is_prod
    error_message = "prod debe activar purge protection y logs."
  }
}

run "la_base_puede_ir_en_otra_region" {
  command = apply

  variables {
    environment       = "dev"
    database_location = "centralus"
  }

  assert {
    condition     = azurerm_resource_group.this.location == "eastus"
    error_message = "El resto del ambiente debe seguir en su region."
  }
  assert {
    condition     = module.database.location == "centralus"
    error_message = "La base debe crearse en database_location."
  }
}

run "la_imagen_debe_ir_por_digest" {
  command = plan

  variables {
    environment = "dev"
    image       = "ghcr.io/eci/ledger:latest"
  }

  expect_failures = [var.image]
}

run "ambiente_desconocido_se_rechaza" {
  command = plan

  variables {
    environment = "staging"
  }

  expect_failures = [var.environment]
}

run "el_tope_de_replicas_protege_el_credito" {
  command = plan

  variables {
    environment  = "prod"
    max_replicas = 10
  }

  expect_failures = [var.max_replicas]
}

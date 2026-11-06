mock_provider "azurerm" {
  mock_resource "azurerm_mssql_server" {
    defaults = {
      id                          = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Sql/servers/sql"
      fully_qualified_domain_name = "sql.database.windows.net"
    }
  }
  mock_resource "azurerm_mssql_database" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Sql/servers/sql/databases/ledger"
    }
  }
}

mock_provider "azapi" {
  mock_resource "azapi_resource" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Sql/servers/sql/databases/ledger"
    }
  }
}

mock_provider "random" {}

variables {
  server_name         = "sql-prueba"
  resource_group_name = "rg"
  location            = "eastus"
}

run "por_defecto_usa_la_oferta_gratuita" {
  command = apply

  assert {
    condition     = length(azapi_resource.free) == 1 && length(azurerm_mssql_database.paid) == 0
    error_message = "Debe crearse solo la base gratuita."
  }
  assert {
    condition     = azapi_resource.free[0].body.properties.useFreeLimit == true
    error_message = "useFreeLimit debe estar activo."
  }
  assert {
    condition     = azapi_resource.free[0].body.properties.freeLimitExhaustionBehavior == "AutoPause"
    error_message = "Al agotar el limite gratis la base debe pausarse, nunca cobrar."
  }
  assert {
    condition     = keys(azapi_resource.free[0].body.properties) == ["freeLimitExhaustionBehavior", "useFreeLimit"]
    error_message = "Azure rechaza valores propios de tamano o pausa en la oferta gratuita con AutoPause."
  }
  assert {
    condition     = strcontains(nonsensitive(output.database_url), "Encrypt=yes&TrustServerCertificate=no")
    error_message = "La conexion debe exigir TLS y validar el certificado."
  }
  assert {
    condition     = azurerm_mssql_server.this.minimum_tls_version == "1.2"
    error_message = "El servidor debe exigir TLS 1.2."
  }
}

run "sin_oferta_gratuita_usa_azurerm" {
  command = apply

  variables {
    use_free_offer = false
  }

  assert {
    condition     = length(azapi_resource.free) == 0 && length(azurerm_mssql_database.paid) == 1
    error_message = "Debe crearse solo la base de pago."
  }
}

run "la_pausa_minima_se_valida" {
  command = plan

  variables {
    auto_pause_delay_minutes = 5
  }

  expect_failures = [var.auto_pause_delay_minutes]
}

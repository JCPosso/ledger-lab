output "database_id" {
  description = "ID de la base de datos."
  value       = local.database_id
}

output "location" {
  description = "Region del servidor."
  value       = azurerm_mssql_server.this.location
}

output "database_url" {
  description = "URL de conexion SQLAlchemy con TLS obligatorio."
  sensitive   = true
  value = format(
    "mssql+pyodbc://%s:%s@%s:1433/%s?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&LoginTimeout=60",
    var.admin_login,
    urlencode(random_password.admin.result),
    azurerm_mssql_server.this.fully_qualified_domain_name,
    var.database_name,
  )
}

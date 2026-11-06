output "app_url" {
  description = "URL publica de la aplicacion."
  value       = module.app.url
}

output "resource_group_name" {
  description = "Grupo de recursos del ambiente."
  value       = azurerm_resource_group.this.name
}

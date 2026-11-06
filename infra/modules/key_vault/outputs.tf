output "id" {
  description = "ID del Key Vault."
  value       = azurerm_key_vault.this.id
}

output "secret_ids" {
  description = "ID sin version de cada secreto, para que la app siempre lea el valor vigente."
  value       = { for name, secret in azurerm_key_vault_secret.this : name => secret.versionless_id }
}

output "resource_group_name" {
  description = "Nome do resource group criado"
  value       = azurerm_resource_group.nano_iaas.name
}

output "storage_account_name" {
  description = "Nome da storage account criada"
  value       = azurerm_storage_account.nano_iaas.name
}

output "storage_account_primary_endpoint" {
  description = "Endpoint primario de blob da storage account"
  value       = azurerm_storage_account.nano_iaas.primary_blob_endpoint
}

output "storage_connection_string" {
  description = "Connection string da storage account (sensivel)"
  value       = azurerm_storage_account.nano_iaas.primary_connection_string
  sensitive   = true
}

output "container_data" {
  description = "Nome do container de dados"
  value       = azurerm_storage_container.nano_iaas_data.name
}

output "container_logs" {
  description = "Nome do container de logs"
  value       = azurerm_storage_container.nano_iaas_logs.name
}

output "container_backups" {
  description = "Nome do container de backups"
  value       = azurerm_storage_container.nano_iaas_backups.name
}

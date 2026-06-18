output "bucket_dev" {
  description = "Nome do bucket dev"
  value       = google_storage_bucket.nano_iaas_dev.name
}

output "bucket_prod" {
  description = "Nome do bucket prod"
  value       = google_storage_bucket.nano_iaas_prod.name
}

output "bucket_backup" {
  description = "Nome do bucket backup"
  value       = google_storage_bucket.nano_iaas_backup.name
}

output "service_account" {
  description = "Email da service account criada"
  value       = google_service_account.nano_iaas_reader.email
}

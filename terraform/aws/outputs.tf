output "bucket_raw" {
  description = "Nome do bucket raw"
  value       = aws_s3_bucket.nano_iaas_raw.bucket
}

output "bucket_processed" {
  description = "Nome do bucket processed"
  value       = aws_s3_bucket.nano_iaas_processed.bucket
}

output "bucket_archive" {
  description = "Nome do bucket archive"
  value       = aws_s3_bucket.nano_iaas_archive.bucket
}

output "iam_user" {
  description = "Usuario IAM criado para o nano-iaas"
  value       = aws_iam_user.nano_iaas_reader.name
}

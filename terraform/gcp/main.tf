terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Bucket GCS - Dev
resource "google_storage_bucket" "nano_iaas_dev" {
  name          = "nano-iaas-dev-${var.project_id}"
  location      = "US-CENTRAL1"
  force_destroy = false

  uniform_bucket_level_access = true

  labels = {
    project     = "nano-iaas"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Bucket GCS - Prod
resource "google_storage_bucket" "nano_iaas_prod" {
  name          = "nano-iaas-prod-${var.project_id}"
  location      = "US-EAST1"
  force_destroy = false

  uniform_bucket_level_access = true

  labels = {
    project     = "nano-iaas"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Bucket GCS - Backup
resource "google_storage_bucket" "nano_iaas_backup" {
  name          = "nano-iaas-backup-${var.project_id}"
  location      = "EUROPE-WEST1"
  force_destroy = false

  uniform_bucket_level_access = true

  labels = {
    project     = "nano-iaas"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Service Account para o nano-iaas com permissao somente leitura
resource "google_service_account" "nano_iaas_reader" {
  account_id   = "nano-iaas-reader"
  display_name = "Nano-IaaS Reader"
  description  = "Service account com permissao de leitura para o nano-iaas"
}

# Permissao de leitura nos buckets
resource "google_storage_bucket_iam_member" "dev_reader" {
  bucket = google_storage_bucket.nano_iaas_dev.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.nano_iaas_reader.email}"
}

resource "google_storage_bucket_iam_member" "prod_reader" {
  bucket = google_storage_bucket.nano_iaas_prod.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.nano_iaas_reader.email}"
}

resource "google_storage_bucket_iam_member" "backup_reader" {
  bucket = google_storage_bucket.nano_iaas_backup.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.nano_iaas_reader.email}"
}

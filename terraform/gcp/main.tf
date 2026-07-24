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

resource "google_project_service" "required" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com"
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# Bucket GCS - Dev
resource "google_storage_bucket" "nano_iaas_dev" {
  name          = "nano-iaas-dev-${var.project_id}"
  location      = "US-CENTRAL1"
  force_destroy = false

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.required]

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
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.required]

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
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.required]

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

  depends_on = [google_project_service.required]
}

resource "google_project_iam_custom_role" "nano_iaas_bucket_lister" {
  project     = var.project_id
  role_id     = "nanoIaasBucketLister"
  title       = "Nano-IaaS Bucket Lister"
  description = "Permite listar e consultar metadados dos buckets GCS"

  permissions = [
    "storage.buckets.get",
    "storage.buckets.list"
  ]

  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "bucket_lister" {
  project = var.project_id
  role    = google_project_iam_custom_role.nano_iaas_bucket_lister.name
  member  = "serviceAccount:${google_service_account.nano_iaas_reader.email}"
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

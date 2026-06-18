terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Resource Group
resource "azurerm_resource_group" "nano_iaas" {
  name     = "nano-iaas-${var.environment}"
  location = var.location

  tags = {
    Project     = "nano-iaas"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Storage Account
resource "azurerm_storage_account" "nano_iaas" {
  name                     = "nanoiaas${var.environment}"
  resource_group_name      = azurerm_resource_group.nano_iaas.name
  location                 = azurerm_resource_group.nano_iaas.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = {
    Project     = "nano-iaas"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Container - Data
resource "azurerm_storage_container" "nano_iaas_data" {
  name                  = "nano-iaas-data"
  storage_account_name  = azurerm_storage_account.nano_iaas.name
  container_access_type = "private"
}

# Container - Logs
resource "azurerm_storage_container" "nano_iaas_logs" {
  name                  = "nano-iaas-logs"
  storage_account_name  = azurerm_storage_account.nano_iaas.name
  container_access_type = "private"
}

# Container - Backups
resource "azurerm_storage_container" "nano_iaas_backups" {
  name                  = "nano-iaas-backups"
  storage_account_name  = azurerm_storage_account.nano_iaas.name
  container_access_type = "private"
}

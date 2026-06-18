variable "location" {
  description = "Regiao Azure"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Ambiente (dev, prod)"
  type        = string
  default     = "dev"
}

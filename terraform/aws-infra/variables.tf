variable "aws_region" {
  description = "Regiao AWS"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Ambiente (dev, prod)"
  type        = string
  default     = "dev"
}

variable "db_name" {
  description = "Nome do banco de dados Postgres"
  type        = string
  default     = "nano_iaas"
}

variable "db_username" {
  description = "Usuario administrador do banco"
  type        = string
  default     = "nano_iaas_admin"
}

variable "backend_image_uri" {
  description = "URI completa da imagem Docker do backend no ECR."
  type        = string
  default     = "488709146598.dkr.ecr.us-east-1.amazonaws.com/nano-iaas-backend-dev:latest"
}

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
  default     = "488709146598.dkr.ecr.us-east-1.amazonaws.com/nano-iaas-backend-dev:git-b7a22a2"
}

variable "api_domain_name" {
  description = "Dominio publico da API usado no certificado ACM e DNS externo"
  type        = string
  default     = "api.nano-iaas.com.br"
}

variable "app_domain_name" {
  description = "Dominio publico do frontend no GitHub Pages"
  type        = string
  default     = "app.nano-iaas.com.br"
}

variable "enable_https" {
  description = "Cria listener HTTPS no ALB usando o certificado ACM ja validado"
  type        = bool
  default     = false
}

variable "acm_certificate_arn" {
  description = "ARN do certificado ACM validado. Se vazio, usa o certificado solicitado por este modulo."
  type        = string
  default     = ""
}

variable "enable_azure_system_fallback" {
  description = "Habilita o fallback sistêmico do Azure na task ECS"
  type        = bool
  default     = false
}

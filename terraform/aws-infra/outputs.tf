output "vpc_id" {
  description = "ID da VPC criada"
  value       = aws_vpc.nano_iaas.id
}

output "db_endpoint" {
  description = "Endpoint de conexao do banco RDS PostgreSQL"
  value       = aws_db_instance.nano_iaas.address
}

output "db_port" {
  description = "Porta do banco RDS PostgreSQL"
  value       = aws_db_instance.nano_iaas.port
}

output "db_secret_arn" {
  description = "ARN do segredo no Secrets Manager contendo as credenciais do banco"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "jwt_secret_arn" {
  description = "ARN do segredo no Secrets Manager contendo a chave de assinatura JWT"
  value       = aws_secretsmanager_secret.jwt_secret.arn
}

output "ecr_repository_url" {
  description = "URL do repositorio ECR para build/push da imagem do backend"
  value       = aws_ecr_repository.nano_iaas_backend.repository_url
}

output "backend_url" {
  description = "URL publica do backend, via Application Load Balancer (HTTP por enquanto)"
  value       = "http://${aws_lb.nano_iaas.dns_name}"
}

output "ecs_cluster_name" {
  description = "Nome do cluster ECS"
  value       = aws_ecs_cluster.nano_iaas.name
}

output "ecs_service_name" {
  description = "Nome do servico ECS do backend"
  value       = aws_ecs_service.nano_iaas_backend.name
}

output "frontend_url" {
  description = "URL publica esperada do frontend apos configurar o CNAME no GitHub Pages/Registro.br"
  value       = "https://${var.app_domain_name}"
}

output "backend_https_url" {
  description = "URL publica esperada da API apos validar ACM e ativar enable_https"
  value       = "https://${var.api_domain_name}"
}

output "api_domain_name" {
  description = "Dominio que deve apontar para o ALB"
  value       = var.api_domain_name
}

output "app_domain_name" {
  description = "Dominio que deve apontar para o GitHub Pages"
  value       = var.app_domain_name
}

output "alb_dns_name" {
  description = "Destino DNS do CNAME api no Registro.br"
  value       = aws_lb.nano_iaas.dns_name
}

output "acm_certificate_arn" {
  description = "ARN do certificado ACM solicitado para a API"
  value       = aws_acm_certificate.api.arn
}

output "acm_dns_validation_records" {
  description = "Registros CNAME que devem ser criados no Registro.br para validar o certificado ACM"
  value = [
    for option in aws_acm_certificate.api.domain_validation_options : {
      name  = option.resource_record_name
      type  = option.resource_record_type
      value = option.resource_record_value
    }
  ]
}


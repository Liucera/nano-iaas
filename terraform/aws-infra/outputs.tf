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

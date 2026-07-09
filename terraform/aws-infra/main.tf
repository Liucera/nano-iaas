terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_secretsmanager_secret" "azure_connection_string" {
  name = "nano-iaas/azure-connection-string-${var.environment}"
}

# ── VPC PRIVADA ──

resource "aws_vpc" "nano_iaas" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = {
    Name      = "nano-iaas-vpc-${var.environment}"
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# Duas subnets privadas em AZs diferentes, exigido pelo grupo de subnets do RDS
resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.nano_iaas.id
  cidr_block        = "10.20.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
  tags = {
    Name      = "nano-iaas-private-a-${var.environment}"
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.nano_iaas.id
  cidr_block        = "10.20.2.0/24"
  availability_zone = data.aws_availability_zones.available.names[1]
  tags = {
    Name      = "nano-iaas-private-b-${var.environment}"
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# Subnets publicas, usadas apenas pelo Load Balancer (que precisa receber trafego da internet)
resource "aws_internet_gateway" "nano_iaas" {
  vpc_id = aws_vpc.nano_iaas.id
  tags = {
    Name      = "nano-iaas-igw-${var.environment}"
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.nano_iaas.id
  cidr_block              = "10.20.101.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags = {
    Name      = "nano-iaas-public-a-${var.environment}"
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.nano_iaas.id
  cidr_block              = "10.20.102.0/24"
  availability_zone       = data.aws_availability_zones.available.names[1]
  map_public_ip_on_launch = true
  tags = {
    Name      = "nano-iaas-public-b-${var.environment}"
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.nano_iaas.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.nano_iaas.id
  }

  tags = {
    Name      = "nano-iaas-public-rt-${var.environment}"
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

resource "aws_db_subnet_group" "nano_iaas" {
  name       = "nano-iaas-db-subnet-${var.environment}"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# Tabela de rotas para as subnets privadas (necessaria para o VPC Endpoint de S3, que e tipo Gateway)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.nano_iaas.id
  tags = {
    Name      = "nano-iaas-private-rt-${var.environment}"
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}

# VPC Endpoint Gateway para S3 - sem custo adicional, evita precisar de NAT Gateway
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.nano_iaas.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# VPC Endpoint Interface para Secrets Manager - custo baixo (~$7-8/mes por AZ), evita NAT Gateway
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.nano_iaas.id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.app_runner.id]
  private_dns_enabled = true
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# VPC Endpoints para ECS Fargate baixar a imagem do ECR e enviar logs, sem precisar de NAT Gateway
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = aws_vpc.nano_iaas.id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.app_runner.id]
  private_dns_enabled = true
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = aws_vpc.nano_iaas.id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.app_runner.id]
  private_dns_enabled = true
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = aws_vpc.nano_iaas.id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.app_runner.id]
  private_dns_enabled = true
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# ── SECURITY GROUPS ──

# Banco: so aceita conexao das tasks do backend (ECS Fargate), nunca da internet
# (nome/descricao do recurso na AWS mantidos como "App Runner" por historico, para nao
# forcar recriacao do security group, que ja esta em uso pelo RDS)
resource "aws_security_group" "db" {
  name        = "nano-iaas-db-sg-${var.environment}"
  description = "Permite acesso ao banco RDS somente do App Runner, sem acesso publico"
  vpc_id      = aws_vpc.nano_iaas.id

  ingress {
    description     = "Postgres a partir das tasks do backend"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_runner.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# Security group das tasks do backend (ECS Fargate) dentro da VPC
resource "aws_security_group" "app_runner" {
  name        = "nano-iaas-apprunner-sg-${var.environment}"
  description = "Security group do App Runner dentro da VPC"
  vpc_id      = aws_vpc.nano_iaas.id

  ingress {
    description     = "HTTP a partir do Load Balancer"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "HTTPS para os VPC Endpoints (Secrets Manager, ECR, CloudWatch Logs), origem nele mesmo"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# Security group do Application Load Balancer, exposto publicamente
resource "aws_security_group" "alb" {
  name        = "nano-iaas-alb-sg-${var.environment}"
  description = "Security group do Load Balancer publico do backend"
  vpc_id      = aws_vpc.nano_iaas.id

  ingress {
    description = "HTTPS publico"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP publico (redireciona para HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# ── SENHA DO BANCO (gerada e guardada no Secrets Manager) ──

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "nano-iaas/db-credentials-${var.environment}"
  description = "Credenciais do banco RDS PostgreSQL do Nano-IaaS"
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db_password.result
    engine   = "postgres"
    host     = aws_db_instance.nano_iaas.address
    port     = 5432
    dbname   = var.db_name
  })
}

# Chave secreta usada para assinar os tokens JWT do backend, gerada automaticamente
resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "jwt_secret" {
  name        = "nano-iaas/jwt-secret-${var.environment}"
  description = "Chave de assinatura dos tokens JWT do Nano-IaaS"
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id     = aws_secretsmanager_secret.jwt_secret.id
  secret_string = random_password.jwt_secret.result
}

# Chave mestra usada para criptografar/descriptografar as credenciais de nuvem
# de cada cliente (padrao Fernet: 32 bytes urlsafe base64), gerada automaticamente
resource "random_bytes" "credentials_encryption_key" {
  length = 32
}

resource "aws_secretsmanager_secret" "credentials_encryption_key" {
  name        = "nano-iaas/credentials-encryption-key-${var.environment}"
  description = "Chave mestra Fernet para criptografar credenciais de nuvem dos clientes"
  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_secretsmanager_secret_version" "credentials_encryption_key" {
  secret_id     = aws_secretsmanager_secret.credentials_encryption_key.id
  secret_string = random_bytes.credentials_encryption_key.base64
}

# ── RDS POSTGRESQL (db.t4g.micro, qualifica para o Free Tier da AWS) ──

resource "aws_db_instance" "nano_iaas" {
  identifier        = "nano-iaas-db-${var.environment}"
  engine            = "postgres"
  engine_version    = "15.7"
  instance_class    = "db.t4g.micro"
  allocated_storage = 20
  storage_type      = "gp2"

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.nano_iaas.name
  vpc_security_group_ids = [aws_security_group.db.id]

  storage_encrypted         = true
  publicly_accessible       = false
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "nano-iaas-final-snapshot-${var.environment}" : null

  backup_retention_period = var.environment == "prod" ? 7 : 1

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# ── ECR (repositorio da imagem Docker do backend) ──

resource "aws_ecr_repository" "nano_iaas_backend" {
  name                 = "nano-iaas-backend-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# ── APPLICATION LOAD BALANCER (exposicao publica do backend) ──

resource "aws_lb" "nano_iaas" {
  name               = "nano-iaas-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_lb_target_group" "nano_iaas_backend" {
  name        = "nano-iaas-backend-tg-${var.environment}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.nano_iaas.id
  target_type = "ip"

  health_check {
    path                = "/login"
    matcher             = "200-499"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}


resource "aws_acm_certificate" "api" {
  domain_name       = var.api_domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_lb_listener" "nano_iaas_http" {
  load_balancer_arn = aws_lb.nano_iaas.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nano_iaas_backend.arn
  }
}


resource "aws_lb_listener" "nano_iaas_https" {
  count = var.enable_https ? 1 : 0

  load_balancer_arn = aws_lb.nano_iaas.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = coalesce(var.acm_certificate_arn, aws_acm_certificate.api.arn)

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nano_iaas_backend.arn
  }
}

# ── ECS FARGATE (backend FastAPI) ──

resource "aws_ecs_cluster" "nano_iaas" {
  name = "nano-iaas-cluster-${var.environment}"

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_cloudwatch_log_group" "nano_iaas_backend" {
  name              = "/ecs/nano-iaas-backend-${var.environment}"
  retention_in_days = 14

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

# Role usada pelo ECS para baixar a imagem do ECR e ler o segredo do Secrets Manager
resource "aws_iam_role" "ecs_execution" {
  name = "nano-iaas-ecs-execution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "nano-iaas-ecs-secrets-${var.environment}"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.db_credentials.arn,
        aws_secretsmanager_secret.jwt_secret.arn,
        aws_secretsmanager_secret.credentials_encryption_key.arn,
        data.aws_secretsmanager_secret.azure_connection_string.arn
      ]
    }]
  })
}

# Role usada pelo CODIGO da aplicacao em execucao (ex: chamadas boto3 para S3)
resource "aws_iam_role" "ecs_task" {
  name = "nano-iaas-ecs-task-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_iam_role_policy" "ecs_task_secrets" {
  name = "nano-iaas-ecs-task-secrets-${var.environment}"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.db_credentials.arn,
        aws_secretsmanager_secret.credentials_encryption_key.arn,
        data.aws_secretsmanager_secret.azure_connection_string.arn
      ]
    }]
  })
}

# Permissao de leitura no S3 para a role da task, equivalente ao usuario nano-iaas-reader
# usado pela CLI, agora aplicada via IAM Role em vez de profile/credenciais locais
resource "aws_iam_role_policy" "ecs_task_s3_read" {
  name = "nano-iaas-ecs-task-s3-read-${var.environment}"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation"
      ]
      Resource = ["*"]
    }]
  })
}

resource "aws_ecs_task_definition" "nano_iaas_backend" {
  family                   = "nano-iaas-backend-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = var.backend_image_uri
      essential = true
      portMappings = [
        { containerPort = 8000, protocol = "tcp" }
      ]
      environment = [
        { name = "DATABASE_SECRET_ARN", value = aws_secretsmanager_secret.db_credentials.arn },
        { name = "AWS_REGION", value = var.aws_region }
      ]
      secrets = [
        { name = "NANO_IAAS_SECRET_KEY", valueFrom = aws_secretsmanager_secret.jwt_secret.arn },
        { name = "NANO_IAAS_ENCRYPTION_KEY", valueFrom = aws_secretsmanager_secret.credentials_encryption_key.arn },
        { name = "AZURE_STORAGE_CONNECTION_STRING", valueFrom = data.aws_secretsmanager_secret.azure_connection_string.arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nano_iaas_backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }
    }
  ])

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

resource "aws_ecs_service" "nano_iaas_backend" {
  name            = "nano-iaas-backend-${var.environment}"
  cluster         = aws_ecs_cluster.nano_iaas.id
  task_definition = aws_ecs_task_definition.nano_iaas_backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups  = [aws_security_group.app_runner.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.nano_iaas_backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.nano_iaas_http]

  tags = {
    Project   = "nano-iaas"
    ManagedBy = "terraform"
  }
}

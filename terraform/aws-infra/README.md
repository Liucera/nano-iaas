# Nano-IaaS — Infraestrutura AWS (VPC + Aurora + App Runner)

Modulo Terraform para provisionamento da infraestrutura de producao do Nano-IaaS.

## O que e criado

- VPC privada (10.0.0.0/16) com 2 subnets privadas
- Security Groups isolados para Aurora e App Runner
- Aurora PostgreSQL Serverless v2 (sem acesso publico)
- Senha gerada automaticamente e armazenada no Secrets Manager
- VPC Connector para o App Runner
- App Runner conectado a VPC, lendo o codigo direto do GitHub

## Pre-requisitos

- Terraform >= 1.0
- AWS CLI configurado com permissoes de administrador
- Conexao GitHub autorizada no App Runner (AWS Console)

## Como usar

```bash
cd terraform/aws-infra
terraform init
terraform plan
terraform apply
```

## Ordem de criacao dos recursos

1. VPC e subnets
2. Security Groups
3. Secrets Manager (senha gerada)
4. Aurora PostgreSQL Serverless v2
5. VPC Connector
6. IAM Role para App Runner
7. App Runner Service

## Custo estimado (us-east-1)

| Recurso | Custo estimado |
|---|---|
| Aurora Serverless v2 (0.5 ACU minimo) | ~$43/mes |
| App Runner (1 vCPU, 2GB) | ~$40/mes |
| Secrets Manager | ~$0.40/mes |
| VPC/NAT Gateway | ~$32/mes |
| Total estimado | ~$115/mes |

## Seguranca

- Aurora sem acesso publico — apenas via VPC
- Senha de 32 caracteres gerada automaticamente
- Credenciais nunca em texto puro no codigo
- Security Groups com regras minimas de acesso
- Criptografia em repouso habilitada no Aurora
- Protecao contra exclusao acidental habilitada

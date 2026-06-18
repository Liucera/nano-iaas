# Nano-IaaS — Terraform

Provisionamento de infraestrutura multi-cloud para o Nano-IaaS.

## Estrutura
terraform/

├── aws/        → Buckets S3 + usuario IAM read-only

├── gcp/        → Buckets GCS + service account read-only

└── azure/      → Storage Account + containers privados

## Pre-requisitos

- Terraform >= 1.0
- Credenciais configuradas para cada cloud

## Como usar

### AWS

```bash
cd terraform/aws
terraform init
terraform plan
terraform apply
```

### GCP

```bash
cd terraform/gcp
terraform init
terraform plan -var="project_id=SEU_PROJECT_ID"
terraform apply -var="project_id=SEU_PROJECT_ID"
```

### Azure

```bash
cd terraform/azure
terraform init
terraform plan
terraform apply
```

## Destruir infraestrutura

```bash
terraform destroy
```

## O que e criado

| Cloud | Recursos |
|---|---|
| AWS | 3 buckets S3 + 1 usuario IAM read-only |
| GCP | 3 buckets GCS + 1 service account read-only |
| Azure | 1 storage account + 3 containers privados |

## Seguranca

- Todos os buckets sao privados
- Acesso somente leitura para o nano-iaas
- Nenhuma credencial no codigo — use variaveis de ambiente

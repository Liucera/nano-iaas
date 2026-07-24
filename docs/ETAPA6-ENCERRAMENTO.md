# Etapa 6 — Encerramento

Data: 24/07/2026
Status: concluída
Progresso geral do projeto: 60%

## Escopo concluído

1. Preparação e auditoria.
2. Validação real da AWS.
3. Validação real do GCP.
4. Validação real do Azure.
5. Validação remota de credenciais antes da persistência.
6. Regressão e segurança multi-cloud.
7. Deploy e smoke em produção.
8. Documentação e encerramento formal.

## Entregas

- AWS, GCP e Azure integrados aos leitores reais.
- Credenciais AWS validadas por STS.
- Credenciais GCP validadas por chamada autenticada ao GCS.
- Azure com connection string e service principal suportados.
- Storage Account incluída no contrato seguro do Azure.
- Credenciais validadas remotamente antes de POST/PUT.
- Segredos armazenados cifrados e respostas mascaradas.
- Três buckets GCP privados, versionados e protegidos contra destruição.
- Service account GCP somente leitura e sem chave persistente.
- IAM mínimo para listagem de buckets e leitura de objetos.
- Health check público em `/health`.
- ALB restrito ao código HTTP `200`.

## Evidências

- PR #22: providers AWS, GCP e Azure.
- PR #23: correção profissional do health check.
- 289 testes aprovados.
- CI aprovado em Python 3.10, 3.11 e 3.12.
- GitGuardian aprovado.
- Terraform AWS e GCP validados.
- Planos pós-deploy sem diferenças.
- Fixtures temporários removidos dos três provedores.

## Produção AWS

- ECS task definition: `nano-iaas-backend-dev:15`.
- Serviço: 1 desejada, 1 executando, 0 pendentes.
- Rollout: `COMPLETED`.
- Imagem: `sha256:e1f76e374bc5194f7071188b8c953d6159905836c1648ce054aebe3b3f5a536e`.
- Health check: `/health`, matcher `200`.
- Terraform state lineage: `6ce1818b-18d2-2a9e-afbd-8640951622e0`.
- Terraform state serial: `132`.
- Terraform state SHA-256: `f0b5adee4a3e5487f8d0fbdb945bec158fe38c8f0c812a111663d0f91f41fdae`.

## GCP

- Projeto: `project-4d8afae3-7bd1-40d5-aec`.
- Buckets: dev, prod e backup.
- Service account: `nano-iaas-reader`.
- Criação de chaves bloqueada pela política organizacional.
- Impersonação temporária validada e posteriormente revogada.
- State lineage: `cc3c79fb-daae-5930-da06-9def95bd9114`.
- State serial: `13`.
- State SHA-256: `bd79f583fcf8660f3c761eb10e506b0b1304937f1a874a0b3b27b378a48794da`.

## Azure

- Leitura real validada com connection string protegida no Secrets Manager.
- Containers de dados, backups e logs acessíveis.
- Service principal implementado e coberto por testes.
- Política de segurança do tenant preservada, sem desativação de controles.

## Observações

Os três avisos da suíte são de depreciações conhecidas do Passlib e FastAPI e não representam falha da Etapa 6.

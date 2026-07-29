# Hibernação emergencial do Nano-IaaS

**Data:** 28/07/2026
**Estado:** infraestrutura cloud hibernada por tempo indeterminado
**Progresso preservado:** 75% do projeto e 50% da Macroetapa 8

## Motivo

A infraestrutura foi hibernada devido ao encerramento iminente do benefício
Free Tier da AWS e à impossibilidade financeira de manter os custos
recorrentes. A decisão evita cobranças e não representa abandono ou perda do
trabalho realizado.

O repositório, o frontend estático, o código Terraform, os states e os backups
foram preservados. A API e os recursos cloud estão intencionalmente
indisponíveis.

## Governança

A hibernação não conclui o Bloco 8.5. A retomada exigirá revisão de custos,
planos Terraform revisados e autorização antes de qualquer recriação.

Os planos destrutivos foram gerados em diretórios temporários, revisados e
executados somente após autorização explícita.

## AWS

- 71 recursos Terraform removidos;
- 53 imagens ECR removidas após preservar a imagem operacional;
- buckets Terraform e o bucket residual `nano-iaas-teste` removidos;
- segredos agendados para exclusão com janela de recuperação;
- auditoria confirmou ausência dos principais recursos faturáveis.

## GCP

- 12 recursos Terraform removidos;
- três buckets vazios removidos;
- permissões IAM, conta de serviço e papel personalizado removidos;
- projeto `project-4d8afae3-7bd1-40d5-aec` preservado;
- faturamento desvinculado e `billingEnabled=false` validado.

## Azure

- três containers confirmados vazios;
- atribuição temporária de leitura removida após a auditoria;
- Storage Account `nanoiaasdev` removida;
- Resource Group `nano-iaas-dev` removido;
- auditoria final não encontrou recursos Nano-IaaS.

## States oficiais pós-hibernação

| Nuvem | Serial | Recursos | SHA-256 |
|---|---:|---:|---|
| AWS | 228 | 0 | `49e9b6ffa99e3a0bf4befde916d5b51b253eca1ab1245c3ca65b47a8ca23d7e9` |
| GCP | 26 | 0 | `d1475502586be1fc6165284d69583589272a1689556932cf946981b769207563` |
| Azure | 13 | 0 | `526650ed52dfbd707605dabef685911f22ff222e000250aa9c86d839c7fdb583` |

Os três states oficiais possuem modo `0600` e lineages preservadas. Cópias pré
e pós-hibernação permanecem armazenadas fora do repositório.

## Artefatos preservados

- imagem Docker operacional por digest imutável;
- backup lógico do PostgreSQL com cinco tabelas, 26 registros e quatro
  sequências;
- 99.425 eventos do CloudWatch em JSONL compactado;
- states das três nuvens anteriores e posteriores à hibernação;
- objetos residuais `metrics.csv` e `users.jsonl`;
- segredo de conexão Azure em arquivo local protegido;
- logs dos `apply` de hibernação.

Nenhum segredo, conteúdo de banco ou backup operacional foi versionado no Git.

## Condições para retomada

1. definir uma fonte sustentável de custeio;
2. revisar preços e planos Terraform antes de qualquer `apply`;
3. reativar faturamento somente após aprovação;
4. recriar a infraestrutura usando os states pós-hibernação;
5. restaurar imagem, banco e segredos dos backups protegidos;
6. revisar DNS, certificados e endpoints;
7. executar testes, smoke tests e planos pós-deploy;
8. atualizar README, ROADMAP e documentação operacional.

Criar outra conta ou usuário para obter novo benefício Free Tier não faz parte
da estratégia de retomada.

## Evidências de recuperação

| Artefato | SHA-256 |
|---|---|
| Imagem Docker operacional | `ebbabd980d6059214dd21647a0f6033a1b261ed63bd4e18549fb5b20f9a895bc` |
| Backup lógico PostgreSQL | `3c17bb911307071bab081cb978566818692385a34bae9e8e90c2df81687f9517` |
| Eventos CloudWatch | `bcd594b9d639a9bdb10a52134c8ac355676997d8a74aadbf4d3249ee02e695ea` |
| `metrics.csv` | `9f42b5e6c4c40c2c92bb9f6bdc118e817cbfa36ce6cc1fb2770965b4f0859e38` |
| `users.jsonl` | `0475464344da5a5eabc84f368152583ad2edc45a542441ee55b18fd5137fb9d6` |

O arquivo do segredo Azure permanece protegido com modo `0600`; seu conteúdo e
hash não são registrados no repositório.

## Validação final

- AWS: auditoria direta dos serviços retornou vazia;
- GCP: recursos ausentes e faturamento desabilitado;
- Azure: Resource Group e Storage Account ausentes;
- states AWS, GCP e Azure com zero recursos gerenciados;
- frontend e repositório preservados;
- percentual formal mantido em 75%.

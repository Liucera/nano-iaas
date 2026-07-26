# Macroetapa 8 — Política de retenção e recuperação

**Data da formalização:** 26/07/2026
**Base oficial de abertura:** `f9c12c7fe0a419cb46bfcf9244dcf93adea6b095`
**Macroetapa:** 8 — Observabilidade e backup
**Bloco:** 8.1 — Baseline, política de retenção e requisitos de recuperação
**Estado após a revisão:** concluído
**Alterações cloud realizadas neste bloco:** nenhuma

## 1. Objetivo

Definir a política operacional de retenção, backup, integridade e recuperação do Nano-IaaS antes de qualquer alteração de infraestrutura.

A política preserva o comportamento read-only do produto, os controles concluídos nas macroetapas anteriores e os states oficiais das três nuvens.

Os valores de RPO e RTO definidos neste documento são objetivos operacionais da fase Beta. Eles não representam SLA comercial.

## 2. Limites

Este bloco é exclusivamente documental e não autoriza:

- `terraform apply`;
- deploy;
- alteração de recurso cloud;
- restauração sobre dados oficiais;
- alteração dos states oficiais;
- mudança no comportamento read-only;
- tratamento dos três warnings conhecidos da suíte;
- recuperação administrativa, recuperação de e-mail ou “Esqueci minha senha”;
- redefinição de senha por e-mail;
- autenticação de dois fatores ou códigos de recuperação;
- integração PagSeguro ou automação PIX;
- antecipação da Macroetapa 9.

O valor `enable_https=true` deve ser preservado em toda revisão futura do Terraform AWS.

## 3. Baseline auditada

### 3.1 Aplicação

- o health check `GET /health` já existe e está validado;
- os providers reais ainda usam `print()`;
- não existe logging estruturado;
- não existe identificador padronizado de correlação;
- não existe medição padronizada de duração das requisições.

Essas lacunas pertencem ao Bloco 8.2. O health check não será reimplementado.

### 3.2 AWS

- CloudWatch Log Group: `/ecs/nano-iaas-backend-dev`;
- retenção atual: 14 dias;
- volume armazenado auditado: aproximadamente 10,7 MB;
- alarmes CloudWatch: inexistentes;
- dashboards CloudWatch: inexistentes;
- Container Insights: desativado;
- RDS disponível e criptografado;
- backup automático RDS: ativo;
- retenção atual do backup RDS: 1 dia;
- recuperação pontual RDS: disponível;
- deletion protection: desativada;
- Multi-AZ: desativado;
- ALB `nano-iaas-alb-dev`: ativo.

### 3.3 GCP

Projeto oficial: `project-4d8afae3-7bd1-40d5-aec`.

Os buckets oficiais de desenvolvimento, produção e backup possuem:

- versionamento ativo;
- soft delete de 604800 segundos, equivalente a sete dias;
- acesso público bloqueado;
- uniform bucket-level access;
- proteção Terraform `prevent_destroy`.

Não existem políticas de alerta, dashboards, uptime checks ou métricas baseadas em logs.

### 3.4 Azure

Recursos auditados:

- Resource Group: `nano-iaas-dev`;
- Storage Account: `nanoiaasdev`;
- região: `eastus`;
- replicação: `Standard_LRS`;
- HTTPS obrigatório: ativo;
- TLS mínimo: 1.2;
- containers privados: `nano-iaas-backups`, `nano-iaas-data` e `nano-iaas-logs`.

Proteções ausentes na abertura da etapa:

- versionamento;
- soft delete de blobs;
- soft delete de containers;
- restauração pontual;
- change feed;
- configurações de diagnóstico;
- alertas;
- Action Groups;
- Log Analytics;
- locks.

Operações Azure dependentes de CLI devem usar PowerShell nativo do Windows. Não será tentado contornar o bloqueio de Acesso Condicional do Azure CLI no WSL. Git e Terraform permanecem exclusivamente no WSL.

## 4. States oficiais de abertura

| Provider | Lineage | Serial | SHA-256 |
|---|---|---:|---|
| AWS | `6ce1818b-18d2-2a9e-afbd-8640951622e0` | 136 | `7fac915f32af222dd2259de1a9ba605f78ed3e590d5f178924db76b8270d68f8` |
| GCP | `cc3c79fb-daae-5930-da06-9def95bd9114` | 13 | `bd79f583fcf8660f3c761eb10e506b0b1304937f1a874a0b3b27b378a48794da` |
| Azure | `59c5cbf0-4dad-22de-e1dd-012eeda6dabb` | 7 | `a5dd8840a81c86cdf4fcd6a61ed57593aebddc4bd3abec47459a52b1e46ab178` |

Caminhos oficiais:

- AWS: `/home/liucera/nano-iaas/terraform/aws-infra/terraform.tfstate`;
- GCP: `/home/liucera/nano-iaas/terraform/gcp/terraform.tfstate`;
- Azure: `/home/liucera/nano-iaas/terraform/azure/terraform.tfstate`.

Esses arquivos não podem ser substituídos, movidos, versionados ou utilizados diretamente em testes de restauração.

## 5. Política aprovada para a Beta

| Ativo | Retenção e proteção exigidas | RPO operacional | RTO operacional |
|---|---|---|---|
| Logs da aplicação no CloudWatch | Retenção explícita de 14 dias, gerenciada por Terraform | Registros recebidos pelo CloudWatch antes do incidente | Consulta restabelecida em até 1 hora |
| Banco RDS | Backup automático por 7 dias e recuperação pontual preservada | Até 5 minutos | Recuperação isolada em até 4 horas |
| Buckets AWS S3 oficiais | Versionamento, criptografia, bloqueio público e `prevent_destroy` preservados; sem nova expiração automática | Última versão anterior ao incidente | Recuperação manual em até 4 horas |
| Buckets GCP oficiais | Versionamento, soft delete de 7 dias, bloqueio público e `prevent_destroy` preservados | Última versão recuperável dentro da janela disponível | Recuperação manual em até 4 horas |
| Containers Azure oficiais | Versionamento e soft delete de blobs e containers por 7 dias | Última versão recuperável dentro da janela disponível | Recuperação manual em até 4 horas |
| States Terraform | Cópia íntegra imediatamente antes de cada `apply`, com verificação posterior | Estado imediatamente anterior ao `apply` | Validação da cópia em até 1 hora |

## 6. Política dos logs

A retenção do Log Group `/ecs/nano-iaas-backend-dev` permanece em 14 dias.

O Bloco 8.2 deverá substituir saídas operacionais por logging estruturado, sanitizado e correlacionado. Logs não podem registrar:

- senhas;
- tokens JWT;
- connection strings;
- access keys;
- service account JSON;
- conteúdo integral de credenciais;
- conteúdo integral dos objetos consultados;
- dados pessoais além do estritamente necessário;
- traces internos não sanitizados em respostas públicas.

O identificador de correlação deverá ser aceito ou gerado pelo backend, devolvido ao cliente e propagado nos registros da requisição. A duração deverá ser registrada em milissegundos.

## 7. Política do RDS

A retenção dos backups automáticos deverá passar de 1 para 7 dias.

A recuperação pontual existente deverá ser preservada. Nenhum teste poderá restaurar sobre a instância oficial.

A validação futura deverá usar destino isolado, identificador próprio e janela de custo previamente revisada. A restauração temporária somente poderá ocorrer depois de plano explícito e autorização.

Multi-AZ não integra os critérios desta macroetapa. Sua ativação não é necessária para concluir a Etapa 8.

## 8. Política dos objetos multi-cloud

### 8.1 AWS

As proteções existentes nos buckets oficiais serão preservadas. Não será adicionada expiração automática de versões neste momento.

### 8.2 GCP

O versionamento, o soft delete de sete dias, o bloqueio público, o uniform bucket-level access e o `prevent_destroy` serão preservados.

### 8.3 Azure

Serão exigidos:

- versionamento de blobs;
- soft delete de blobs por sete dias;
- soft delete de containers por sete dias.

Change feed e restauração pontual da conta não são requisitos da Etapa 8. Não devem ser adicionados sem nova justificativa técnica, revisão de custo e revisão do plano.

## 9. Política dos states

Antes de qualquer `apply` futuro:

1. confirmar o caminho oficial do state;
2. calcular SHA-256;
3. registrar lineage e serial;
4. criar uma cópia fora do repositório;
5. restringir diretório e arquivo ao usuário local;
6. validar o hash da cópia;
7. revisar integralmente o plano;
8. somente então solicitar autorização para o `apply`.

Diretório planejado para as cópias:

`/home/liucera/nano-iaas-state-backups/etapa8/<provider>/`

Requisitos:

- diretório com permissão `700`;
- arquivos com permissão `600`;
- nome contendo provider, data, hora, serial e indicação pré ou pós-apply;
- proibição de commit, upload público ou inclusão em logs;
- nenhuma exibição do conteúdo do state;
- registro apenas de caminho, lineage, serial e SHA-256.

Após cada `apply` autorizado, o novo state deverá ter lineage, serial e SHA-256 registrados e deverá receber uma nova cópia íntegra.

## 10. Validação controlada de recuperação

A validação de recuperação ocorrerá no Bloco 8.6 e deverá respeitar:

- uso de cópias, recursos temporários ou dados sintéticos;
- proibição de sobrescrever arquivos, buckets, containers, banco ou states oficiais;
- identificação clara de todo recurso temporário;
- revisão prévia de custo;
- plano de remoção controlada;
- evidências sem segredos ou conteúdo sensível;
- comparação de hash, lineage e serial para os states;
- confirmação de leitura do recurso restaurado;
- registro do tempo utilizado para comparação com o RTO.

A remoção de recursos temporários dependerá da identificação exata dos alvos e da mesma autorização concedida ao teste.

## 11. Canal de alerta

O canal operacional será definido e validado no Bloco 8.4.

Requisitos mínimos:

- não registrar endereço pessoal diretamente no código;
- configuração por variável ou Terraform apropriado;
- confirmação explícita da assinatura;
- mensagem de teste controlada;
- alarmes limitados a condições acionáveis;
- documentação do responsável pelo recebimento.

## 12. Controle de custos

Para manter o escopo e os custos controlados:

- usar preferencialmente métricas nativas já disponíveis;
- manter Container Insights desativado nesta etapa;
- não ativar Multi-AZ;
- não exigir Log Analytics no Azure;
- não exigir change feed ou restauração pontual Azure;
- limitar dashboards e alarmes aos critérios formais;
- revisar custos e todos os planos antes de qualquer `apply`;
- remover recursos temporários de recuperação após a validação autorizada.

## 13. Critério de conclusão do Bloco 8.1

O Bloco 8.1 será considerado concluído somente quando:

- esta política estiver revisada e versionada;
- baseline das três nuvens estiver registrado;
- retenções mínimas estiverem definidas;
- RPO e RTO estiverem definidos;
- regras para os states estiverem definidas;
- método de recuperação controlada estiver definido;
- limites de custo estiverem definidos;
- nenhuma alteração cloud tiver sido realizada;
- README e ROADMAP registrarem a conclusão e o percentual correspondente.

## 14. Próximo bloco

Após o encerramento formal do Bloco 8.1, o próximo trabalho executável será o Bloco 8.2 — Logging estruturado, sanitizado e correlacionado.

Nenhuma alteração cloud será necessária para iniciar o Bloco 8.2.

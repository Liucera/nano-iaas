# Roadmap oficial de preparação para lançamento — Nano-IaaS

**Última atualização:** 26/07/2026
**Percentual total formal do projeto:** **75%**

## Governança

O projeto segue uma sequência fixa e autoritativa de 10 macroetapas. Cada macroetapa representa 10% do total, e nenhuma macroetapa posterior deve ser iniciada antes da conclusão formal da anterior.

Os estados têm os seguintes significados:

- `[x]`: macroetapa formalmente concluída — 100% da macroetapa e 10% do projeto;
- `[~]`: macroetapa em andamento — recebe percentual somente por entregas funcionais formalmente concluídas;
- `[ ]`: macroetapa não iniciada — 0%.

Auditorias, planejamento, preparação de ambiente e criação de worktree não contam como conclusão funcional. A ordem, o número e o peso das macroetapas não podem ser alterados sem uma revisão formal deste plano.

## Situação das 10 macroetapas

| Nº | Macroetapa | Status | Percentual individual | Resumo |
|---:|---|:---:|---:|---|
| 1 | Rate limit em produção | `[x]` | 100% da macroetapa (10% do projeto) | Rate limit ativado e validado em produção. |
| 2 | Frontend em domínio próprio | `[x]` | 100% da macroetapa (10% do projeto) | Aplicativo e API disponíveis em domínios próprios com HTTPS. |
| 3 | Domínio principal | `[x]` | 100% da macroetapa (10% do projeto) | Site institucional principal publicado no Cloudflare Pages e domínio principal concluído formalmente. |
| 4 | Telas essenciais | `[x]` | 100% da macroetapa (10% do projeto) | Os seis blocos foram implantados, validados e concluídos formalmente. |
| 5 | Restrições S3 | `[x]` | 100% da macroetapa (10% do projeto) | Leitura limitada a buckets oficiais e ao prefixo `dados/`, com mínimo privilégio validado em produção. |
| 6 | Validação AWS/GCP/Azure | `[x]` | 100% da macroetapa (10% do projeto) | Oito blocos concluídos, implantados e validados formalmente. |
| 7 | Segurança e auditoria | `[x]` | 100% da macroetapa (10% do projeto) | Oito blocos concluídos, implantados e validados formalmente. |
| 8 | Observabilidade e backup | `[~]` | 50% da macroetapa (5% do projeto) | Blocos 8.1 a 8.4 concluídos; observabilidade e canal operacional AWS ativos. |
| 9 | Deploy final e smoke tests | `[ ]` | 0% (0% do projeto) | Não iniciada formalmente. |
| 10 | Checklist de lançamento e comunicação | `[ ]` | 0% (0% do projeto) | Não iniciada formalmente. |

## Macroetapas concluídas

### 1. Rate limit em produção `[x]`

O rate limit foi ativado em produção e validado quanto ao fluxo normal de autenticação, bloqueio HTTP 429, cabeçalho `Retry-After` e ausência de regressões.

### 2. Frontend em domínio próprio `[x]`

O aplicativo e a API estão disponíveis por HTTPS em seus domínios próprios. Os fluxos essenciais de cadastro, login, sessão, consulta do usuário e logout foram validados no escopo formal desta macroetapa.

### 3. Domínio principal `[x]`

O domínio principal foi concluído formalmente. A situação institucional atual é:

- site institucional principal: Cloudflare Pages;
- domínio principal: <https://nano-iaas.com.br>;
- aplicativo: <https://app.nano-iaas.com.br>;
- API: <https://api.nano-iaas.com.br>.

## Macroetapa 4 — Telas essenciais `[x]`

A macroetapa 4 foi concluída formalmente. Cadastro, credenciais AWS, GCP e Azure, atualização do próprio plano e revisão geral das mensagens de erro e sucesso foram implantados e validados no escopo definido.

O fluxo comercial vigente mantém os planos Gratuito, Popular e Premium e os valores já definidos no servidor. A mudança direta é permitida somente para o Gratuito ou para manter o plano atual. Popular e Premium dependem de solicitação PIX pendente e aprovação administrativa manual; a solicitação isolada não altera o plano. Nenhum gateway ou regra comercial nova integra este bloco.

Referência operacional de conclusão:

- `main` e frontend publicado: `07d111bd9122cc55b6b54756c2be2337eaf1a0f1`;
- backend em produção: ECS task definition `nano-iaas-backend-dev:12`;
- imagem imutável: `488709146598.dkr.ecr.us-east-1.amazonaws.com/nano-iaas-backend-dev@sha256:51852fd81212d6c2c143d18d703492167d30dd6f3b2af31404999d922c8a047e`;
- rollout ECS concluído, uma tarefa em execução, nenhum pending e target saudável no ALB.

Subitens previstos, na ordem de execução controlada:

- Cadastro `[x]`;
- Credenciais AWS `[x]`;
- Credenciais GCP `[x]`;
- Credenciais Azure `[x]`;
- Atualização do próprio plano `[x]`;
- Revisão geral das mensagens de erro e sucesso `[x]`.

Seis dos seis blocos internos estão formalmente concluídos. Isso representa 100% da macroetapa 4 e 10% do projeto.

### Evidência de conclusão do bloco 4.5

Em 21/07/2026, o fluxo de atualização do próprio plano foi validado de forma autenticada e somente leitura com um usuário comum. `GET /me` e `GET /me/plano/opcoes` responderam HTTP 200; a estrutura dos planos, os valores e os modos de ativação foram confirmados; o frontend preservou a filtragem do plano atual; e nenhum segredo foi exposto. A validação não alterou plano, solicitação PIX ou qualquer dado persistente.

### Evidência de conclusão do bloco 4.6

A revisão geral das mensagens foi implementada, implantada e validada. Ela inclui:

- padronização de português, acentuação e fallbacks para HTTP 400, 401, 403, 404, 409, 422, 429, 500 e 502;
- preservação de `Retry-After` e tratamento controlado de falhas de rede;
- compatibilidade temporária com respostas antigas sem acentuação;
- allowlist para erros operacionais públicos e sanitização de `ValueError` desconhecido;
- semântica acessível com `role`, `aria-live`, `aria-atomic` e foco no status principal de erro;
- 256 testes aprovados, incluindo execução comportamental do JavaScript real com Node e sem rede externa.

A imagem oficial Alpine foi fixada por digest e publicada de forma imutável no ECR. O scan ECR do manifest executável terminou sem findings. O Docker Scout registrou somente o HIGH CVE-2024-23342 em `ecdsa 0.19.2`; o risco foi documentado como não alcançável pelo fluxo atual, pois o backend restringe tokens a `HS256`.

O Terraform apply criou uma task definition e atualizou o serviço sem destruições. O ECS alcançou rollout `COMPLETED` na revisão `nano-iaas-backend-dev:12`, com uma tarefa em execução, nenhum pending e target saudável. Os smoke tests públicos e autenticados confirmaram HTTP 200 para documentação, OpenAPI, login, perfil e opções de plano; HTTP 401 sem token; HTTP 403 para auditoria por usuário comum; HTTP 422 para requisição inválida antes de persistência; e ausência de segredos nas respostas. Nenhum plano, PIX ou dado persistente foi alterado.

## Macroetapa 5 — Restrições S3 `[x]`

A macroetapa 5 foi concluída formalmente após auditoria, implementação em worktree isolado, revisão, testes, duas PRs, implantação controlada e validação em produção.

Entregas concluídas:

- PR [#19](https://github.com/Liucera/nano-iaas/pull/19): validação de caminhos S3, prefixo obrigatório `dados/`, allowlist de buckets, sanitização de erros AWS e IAM de mínimo privilégio;
- PR [#20](https://github.com/Liucera/nano-iaas/pull/20): provisionamento dos três buckets oficiais com controles de segurança;
- remoção de `s3:ListAllMyBuckets`, recursos `*` e qualquer permissão `PutObject` ou `DeleteObject`;
- `ListBucket` limitado a `dados/` e `GetObject` limitado a `dados/*`;
- bloqueio de buckets não oficiais e de caminhos fora do prefixo permitido.

Referência operacional:

- `main`: `07a8e9a39b2cec0a3eb2249219e46ab07f8450cc`;
- ECS task definition: `nano-iaas-backend-dev:13`;
- imagem: `nano-iaas-backend-dev@sha256:34015677fc5e7489717a696561dfccd13c6ad246f8a4c7681543335bb4de9c91`;
- manifest `linux/amd64`: `sha256:541bdb75a69d7f2f88c54972c4e259ae6948fea8c97e0d22ea128f56c2535252`;
- scan ECR concluído sem findings;
- 271 testes aprovados, com três warnings preexistentes.

Controles implantados nos buckets `nano-iaas-raw-dev`, `nano-iaas-processed-dev` e `nano-iaas-archive-dev`:

- bloqueio público integral;
- criptografia AES256;
- versionamento habilitado;
- propriedade `BucketOwnerEnforced`;
- proteção Terraform `prevent_destroy`;
- leitura sistêmica restrita ao prefixo `dados/`.

O apply controlado concluiu `16 added, 2 changed, 1 destroyed`, sendo a destruição exclusivamente a substituição esperada da task definition ECS. O state oficial preservou a lineage `6ce1818b-18d2-2a9e-afbd-8640951622e0` e avançou para o serial `122`. Foi criado backup exclusivo anterior ao apply. O plano posterior retornou `No changes`, e o hash do state permaneceu inalterado durante essa verificação.

Validações em produção:

- rollout ECS `COMPLETED`, desired 1, running 1 e pending 0;
- target do ALB saudável;
- login e `GET /me` com usuário comum responderam HTTP 200;
- `GET /audit` com usuário comum respondeu HTTP 403;
- simulador IAM permitiu `ListBucket` e `GetObject` somente em `dados/`;
- outros prefixos, bucket não oficial, `PutObject` e `DeleteObject` resultaram em `implicitDeny`;
- nenhum plano, PIX, credencial cloud ou dado persistente foi alterado.

A senha da conta administrativa permanece indisponível como pendência operacional preexistente. Não houve redefinição de senha nem alteração de autenticação, banco ou secrets nesta macroetapa. O smoke administrativo foi substituído por testes automatizados, smoke com usuário comum e validação direta da política IAM efetiva. O bucket legado `nano-iaas-teste` permaneceu intocado e fora da allowlist oficial.

## Macroetapa 6 — Validação AWS/GCP/Azure `[x]`

A Macroetapa 6 foi concluída formalmente em 24/07/2026, com 8/8 blocos:

1. Preparação e auditoria.
2. Validação real da AWS.
3. Validação real do GCP.
4. Validação real do Azure.
5. Validação remota de credenciais antes da persistência.
6. Regressão e segurança multi-cloud.
7. Deploy e smoke em produção.
8. Documentação e encerramento formal.

Evidências de conclusão:

- PRs #22, #23 e #24 integradas;
- 289 testes aprovados;
- CI aprovado em Python 3.10, 3.11 e 3.12;
- GitGuardian aprovado;
- ECS `nano-iaas-backend-dev:15`, com rollout `COMPLETED`;
- imagem `sha256:e1f76e374bc5194f7071188b8c953d6159905836c1648ce054aebe3b3f5a536e`;
- health check `GET /health`, matcher HTTP `200`;
- states oficiais AWS e GCP preservados e auditados;
- planos pós-deploy sem diferenças.

O registro técnico completo está em [`docs/ETAPA6-ENCERRAMENTO.md`](docs/ETAPA6-ENCERRAMENTO.md).

## Repositórios oficiais

As fontes oficiais foram verificadas pelos remotos e responsabilidades publicadas:

| Repositório | Função oficial |
|---|---|
| [`Liucera/nano-iaas`](https://github.com/Liucera/nano-iaas) | Código do produto, backend, frontend autenticado, CLI, providers, testes, infraestrutura Terraform e origem do build/deploy do aplicativo e da API. O frontend legado usa GitHub Pages em `main:/docs`. |
| [`Liucera/Liucera.github.io`](https://github.com/Liucera/Liucera.github.io) | Código do site institucional oficial do Nano-IaaS, publicado no domínio principal pelo Cloudflare Pages. |

É proibido misturar alterações, histórico, branches, PRs ou operações de deploy entre esses repositórios. Mudanças de código, infraestrutura e deploy do aplicativo/API pertencem ao `Liucera/nano-iaas`; mudanças do site institucional pertencem ao `Liucera/Liucera.github.io`.

## Macroetapa 7 — Segurança e auditoria `[x]`

A Macroetapa 7 foi concluída formalmente em 25/07/2026. Seu objetivo foi fortalecer os controles de segurança da aplicação e tornar a trilha de auditoria consistente, sanitizada, administrável e verificável, sem repetir entregas das macroetapas anteriores.

### Blocos concluídos

1. Baseline e inventário de segurança.
2. Headers HTTP e CORS restritivo.
3. Autenticação e administração seguras.
4. Centralização, sanitização e cobertura da auditoria.
5. Consulta administrativa de auditoria segura.
6. Higiene do repositório e dependências.
7. Regressão, revisão do plano, deploy controlado e smoke.
8. Documentação e encerramento formal.

### Resultado

- headers HTTP de segurança validados em produção;
- CORS limitado a origens, métodos e headers autorizados;
- JWT fortalecido e bootstrap administrativo sem credencial fixa;
- auditoria centralizada, sanitizada e restrita ao administrador;
- consulta administrativa paginada e auditada;
- `audit.log` removido do versionamento;
- varredura do repositório sem padrões sensíveis;
- dependências verificadas e achado não alcançável justificado;
- 302 testes aprovados localmente;
- CI aprovado em Python 3.10, 3.11 e 3.12;
- GitGuardian aprovado;
- plano Terraform revisado antes do apply;
- produção implantada na task definition `nano-iaas-backend-dev:16`;
- smoke tests não destrutivos aprovados;
- plano pós-deploy sem diferenças.

As evidências completas estão registradas em `docs/ETAPA7-ENCERRAMENTO.md`.

## Macroetapa 8 — Observabilidade e backup `[~]`

A Macroetapa 8 foi aberta em 26/07/2026, sobre a base oficial `f9c12c7fe0a419cb46bfcf9244dcf93adea6b095`. Seu objetivo é implantar observabilidade operacional e proteção de dados com retenção explícita, alertas úteis, preservação dos states e recuperação controlada, sem alterar o comportamento read-only do produto.

O Bloco 8.1 foi concluído com baseline das três nuvens, retenções mínimas, RPO, RTO, regras de integridade dos states, método de recuperação controlada e limites de custo. A política aprovada está em [`docs/ETAPA8-POLITICA-RETENCAO-RECUPERACAO.md`](docs/ETAPA8-POLITICA-RETENCAO-RECUPERACAO.md).

O Bloco 8.2 foi concluído com logging JSON estruturado e sanitizado, correlação por `X-Request-ID`, duração das requisições e substituição dos `print()` nos providers reais.

O Bloco 8.3 foi concluído com o dashboard `nano-iaas-operations-dev` e sete alarmes CloudWatch para disponibilidade, erros, latência, ECS e RDS. Foram preservados Container Insights desativado e o uso exclusivo de métricas nativas. O custo incremental foi revisado dentro da franquia vigente. O plano apresentou 8 recursos para criar, nenhum para alterar ou destruir; o `apply` foi autorizado e o plano posterior retornou `No changes`.

A validação confirmou os sete alarmes em estado `OK`, ECS 1/1/0, rollout concluído, task definition `nano-iaas-backend-dev:16`, target saudável, RDS disponível e health check aprovado. Foram aprovados 316 testes locais, CI em Python 3.10, 3.11 e 3.12 e GitGuardian no PR #29. O state AWS preservou a lineage `6ce1818b-18d2-2a9e-afbd-8640951622e0`, avançou para o serial `145` e recebeu backups íntegros antes e depois do `apply`.

O Bloco 8.4 foi concluído com retenção explícita de 14 dias, tópico SNS operacional e os sete alarmes ligados aos estados `ALARM` e `OK`, sem ação para `INSUFFICIENT_DATA`. A assinatura foi confirmada e uma mensagem controlada foi recebida. O plano apresentou 1 criação, 7 alterações in-place e nenhuma destruição; o plano posterior retornou `No changes`. Foram aprovados 318 testes locais, CI em Python 3.10, 3.11 e 3.12 e GitGuardian no PR #31. O state AWS avançou para o serial `154`, com SHA-256 `d56a167776e4db498a6c48062e9cdae1e9ae65a38a57c9126cfc425edfd61342`.

Para acompanhamento interno, os oito blocos possuem peso igual de 12,5% da macroetapa, equivalente a 1,25% do projeto por bloco. O progresso atual da Macroetapa 8 é **50%**.

### Blocos planejados

1. Baseline, política de retenção e requisitos de recuperação. `[x]`
2. Logging estruturado, sanitizado e correlacionado. `[x]`
3. Dashboard, métricas e alarmes operacionais da produção AWS. `[x]`
4. Retenção de logs e canal de alerta operacional. `[x]`
5. Proteção de dados e backups em AWS, GCP e Azure. `[ ]`
6. Integridade dos states e validação controlada de recuperação. `[ ]`
7. Regressão, revisão de custos e planos, deploy controlado e smoke. `[ ]`
8. Documentação e encerramento formal. `[ ]`

### Critérios de conclusão

- logs estruturados sem segredos ou dados excessivos;
- correlação e duração das requisições;
- dashboard e alarmes de disponibilidade, erros, latência, ECS e RDS;
- canal de alerta operacional validado;
- retenção explícita e gerenciada por Terraform;
- RDS com recuperação mínima de sete dias;
- proteções existentes na AWS e no GCP preservadas;
- Azure com versionamento e soft delete;
- states oficiais preservados e acompanhados por backups íntegros;
- recuperação validada sem tocar em dados oficiais;
- custos e planos revisados antes de qualquer `apply`;
- testes, CI, GitGuardian e smoke aprovados;
- plano pós-deploy sem diferenças;
- nenhuma antecipação da Macroetapa 9.

### Restrições de execução

- preservar `enable_https=true`, os controles de segurança concluídos e o comportamento read-only;
- preservar e auditar os states oficiais das três nuvens;
- não executar `apply`, deploy ou alteração cloud antes da revisão dos planos;
- não repetir auditorias das Macroetapas 6 e 7 enquanto a base permanecer inalterada;
- usar PowerShell nativo do Windows para operações Azure dependentes de CLI, sem contornar o Acesso Condicional;
- manter Git e Terraform exclusivamente no WSL;
- não tratar recuperação administrativa, recuperação de e-mail, “Esqueci minha senha”, redefinição por e-mail, 2FA, códigos de recuperação ou PagSeguro;
- não ampliar o escopo para tratar os três warnings conhecidos da suíte;
- somente no encerramento da Macroetapa 8, revisar formalmente o roadmap para concentrar recuperação de acesso, 2FA e PagSeguro na nova Macroetapa 9 e consolidar deploy final, smoke, checklist e comunicação na nova Macroetapa 10, sem implementar esses itens nesta macroetapa;
- não antecipar a Macroetapa 9.

## Macroetapas futuras

As macroetapas abaixo ainda não foram iniciadas formalmente e não devem ter sua implementação antecipada:

9. Deploy final e smoke tests.
10. Checklist de lançamento e comunicação.

## Método de cálculo

As 10 macroetapas possuem o mesmo peso de 10%:

- 7 macroetapas concluídas × 10% = 70%;
- 4 de 8 blocos da Macroetapa 8 concluídos = 5%;
- macroetapas 9 e 10 não iniciadas = 0%.

**PERCENTUAL TOTAL FORMAL DO PROJETO: 75%**

Percentuais antigos calculados com versões anteriores do roadmap, incluindo estimativas próximas de 92%, não representam esta sequência oficial de preparação para lançamento e não devem ser reutilizados.

## Próxima ação autorizável

1. Iniciar o Bloco 8.5 — Proteção de dados e backups em AWS, GCP e Azure.
2. Identificar os recursos Terraform exatos de cada nuvem antes de preparar alterações.
3. Preservar as proteções existentes na AWS e no GCP e o comportamento read-only.
4. Usar PowerShell nativo do Windows para Azure e revisar custos e planos antes de qualquer `apply`.
5. Não antecipar os Blocos 8.6 a 8.8.

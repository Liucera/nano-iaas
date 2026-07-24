# Roadmap oficial de preparação para lançamento — Nano-IaaS

**Última atualização:** 24/07/2026
**Percentual total formal do projeto:** **60%**

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
| 7 | Segurança e auditoria | `[ ]` | 0% (0% do projeto) | Não iniciada formalmente. |
| 8 | Observabilidade e backup | `[ ]` | 0% (0% do projeto) | Não iniciada formalmente. |
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

## Macroetapas futuras

As macroetapas abaixo ainda não foram iniciadas formalmente e não devem ter sua implementação antecipada:

7. Segurança e auditoria.
8. Observabilidade e backup.
9. Deploy final e smoke tests.
10. Checklist de lançamento e comunicação.

A Macroetapa 7 possui apenas o objetivo nominal “Segurança e auditoria”. Seus blocos e critérios específicos ainda não estão definidos neste roadmap; nenhuma implementação técnica deve começar antes dessa definição formal.

## Método de cálculo

As 10 macroetapas possuem o mesmo peso de 10%:

- 6 macroetapas concluídas × 10% = 60%;
- macroetapa 6 concluída, implantada e validada = 10%;
- macroetapas 7 a 10 não iniciadas = 0%.

**PERCENTUAL TOTAL FORMAL DO PROJETO: 60%**

Percentuais antigos calculados com versões anteriores do roadmap, incluindo estimativas próximas de 92%, não representam esta sequência oficial de preparação para lançamento e não devem ser reutilizados.

## Próxima ação autorizável

1. Planejar formalmente a Macroetapa 7 — Segurança e auditoria.
2. Definir e aprovar seus blocos e critérios de conclusão antes de qualquer implementação técnica.
3. Preservar o comportamento read-only e impedir exposição de credenciais, segredos ou erros operacionais.
4. Implementar mudanças somente em worktree isolado, com testes e revisão antes de qualquer alteração cloud.
5. Não antecipar a Macroetapa 8 antes da conclusão formal da Macroetapa 7.

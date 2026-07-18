# Roadmap oficial de preparação para lançamento — Nano-IaaS

**Última atualização:** 18/07/2026
**Percentual total formal do projeto:** **35%**

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
| 4 | Telas essenciais | `[~]` | 50% da macroetapa (5% do projeto) | Cadastro, Credenciais AWS e Credenciais GCP concluídos; Credenciais Azure em andamento. |
| 5 | Restrições S3 | `[ ]` | 0% (0% do projeto) | Não iniciada formalmente. |
| 6 | Validação AWS/GCP/Azure | `[ ]` | 0% (0% do projeto) | Não iniciada formalmente. |
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

## Macroetapa 4 — Telas essenciais `[~]`

A macroetapa 4 está em andamento. Cadastro, Credenciais AWS e Credenciais GCP foram concluídos formalmente. O bloco atual é Credenciais Azure e contempla somente cadastro, listagem segura, substituição e exclusão da credencial. A validação real contra a Microsoft Azure permanece reservada para a Macroetapa 6.

Referência operacional vigente:

- commit da `main`: `ad327c76f8dc099f3d2df4be276ccd0a41025605`;
- backend em produção: ECS task definition `nano-iaas-backend-dev:9`.

Subitens previstos, na ordem de execução controlada:

- Cadastro `[x]`;
- Credenciais AWS `[x]`;
- Credenciais GCP `[x]`;
- Credenciais Azure `[~]`;
- Atualização do próprio plano `[ ]`;
- Revisão geral das mensagens de erro e sucesso `[ ]`.

Três dos seis blocos internos estão formalmente concluídos. Isso representa 50% da macroetapa 4 e 5% do projeto.

## Repositórios oficiais

As fontes oficiais foram verificadas pelos remotos e responsabilidades publicadas:

| Repositório | Função oficial |
|---|---|
| [`Liucera/nano-iaas`](https://github.com/Liucera/nano-iaas) | Código do produto, backend, frontend autenticado, CLI, providers, testes, infraestrutura Terraform e origem do build/deploy do aplicativo e da API. O frontend legado usa GitHub Pages em `main:/docs`. |
| [`Liucera/Liucera.github.io`](https://github.com/Liucera/Liucera.github.io) | Código do site institucional oficial do Nano-IaaS, publicado no domínio principal pelo Cloudflare Pages. |

É proibido misturar alterações, histórico, branches, PRs ou operações de deploy entre esses repositórios. Mudanças de código, infraestrutura e deploy do aplicativo/API pertencem ao `Liucera/nano-iaas`; mudanças do site institucional pertencem ao `Liucera/Liucera.github.io`.

## Macroetapas futuras

As macroetapas abaixo ainda não foram iniciadas formalmente e não devem ter sua implementação antecipada:

5. Restrições S3.
6. Validação AWS/GCP/Azure.
7. Segurança e auditoria.
8. Observabilidade e backup.
9. Deploy final e smoke tests.
10. Checklist de lançamento e comunicação.

## Método de cálculo

As 10 macroetapas possuem o mesmo peso de 10%:

- 3 macroetapas concluídas × 10% = 30%;
- 3 dos 6 blocos da macroetapa 4 concluídos = 5%;
- macroetapas 5 a 10 não iniciadas = 0%.

**PERCENTUAL TOTAL FORMAL DO PROJETO: 35%**

Percentuais antigos calculados com versões anteriores do roadmap, incluindo estimativas próximas de 92%, não representam esta sequência oficial de preparação para lançamento e não devem ser reutilizados.

## Próxima ação autorizável

1. Concluir a implementação e a validação local do bloco Credenciais Azure.
2. Submeter uma única PR para revisão, sem auto-merge.
3. Não iniciar Atualização do próprio plano antes da conclusão formal do bloco Azure.
4. Não executar validação real contra a Microsoft Azure antes da Macroetapa 6.

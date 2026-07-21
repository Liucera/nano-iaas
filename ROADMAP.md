# Roadmap oficial de preparação para lançamento — Nano-IaaS

**Última atualização:** 21/07/2026
**Percentual total formal do projeto:** **38,33%**

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
| 4 | Telas essenciais | `[~]` | 83,33% da macroetapa (8,33% do projeto) | Cadastro, credenciais AWS/GCP/Azure e atualização do próprio plano concluídos; revisão geral das mensagens pendente. |
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

A macroetapa 4 está em andamento. Cadastro, credenciais AWS, GCP e Azure e atualização do próprio plano foram concluídos formalmente. O bloco atual é a Revisão geral das mensagens de erro e sucesso.

O fluxo comercial vigente mantém os planos Gratuito, Popular e Premium e os valores já definidos no servidor. A mudança direta é permitida somente para o Gratuito ou para manter o plano atual. Popular e Premium dependem de solicitação PIX pendente e aprovação administrativa manual; a solicitação isolada não altera o plano. Nenhum gateway ou regra comercial nova integra este bloco.

Referência operacional vigente:

- commit da `main` e frontend publicado: `d6de052e361031205fbc515f9741606ea38bcac5`;
- backend em produção: ECS task definition `nano-iaas-backend-dev:11`, imagem `git-5391c5a`;
- a publicação da revisão posterior do backend permanece bloqueada pelo critério de zero vulnerabilidades críticas.

Subitens previstos, na ordem de execução controlada:

- Cadastro `[x]`;
- Credenciais AWS `[x]`;
- Credenciais GCP `[x]`;
- Credenciais Azure `[x]`;
- Atualização do próprio plano `[x]`;
- Revisão geral das mensagens de erro e sucesso `[ ]`.

Cinco dos seis blocos internos estão formalmente concluídos. Isso representa 83,33% da macroetapa 4 e 8,33% do projeto.

### Evidência de conclusão do bloco 4.5

Em 21/07/2026, o fluxo de atualização do próprio plano foi validado de forma autenticada e somente leitura com um usuário comum. `GET /me` e `GET /me/plano/opcoes` responderam HTTP 200; a estrutura dos planos, os valores e os modos de ativação foram confirmados; o frontend preservou a filtragem do plano atual; e nenhum segredo foi exposto. A validação não alterou plano, solicitação PIX ou qualquer dado persistente.

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
- 5 dos 6 blocos da macroetapa 4 concluídos = 8,33%;
- macroetapas 5 a 10 não iniciadas = 0%.

**PERCENTUAL TOTAL FORMAL DO PROJETO: 38,33%**

Percentuais antigos calculados com versões anteriores do roadmap, incluindo estimativas próximas de 92%, não representam esta sequência oficial de preparação para lançamento e não devem ser reutilizados.

## Próxima ação autorizável

1. Iniciar o bloco Revisão geral das mensagens de erro e sucesso.
2. Inventariar e padronizar mensagens visíveis, fallbacks, acessibilidade e tratamento dos códigos HTTP, sem alterar contratos da API.
3. Preservar a sanitização de dados sensíveis e as proteções administrativas e assíncronas já integradas.
4. Não alterar regras comerciais, permissões, gateways, fluxos de pagamento ou recursos cloud neste bloco.
5. Submeter a implementação em uma única PR para revisão, sem auto-merge.

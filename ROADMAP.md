# Roadmap oficial de preparação para lançamento — Nano-IaaS

**Última atualização:** 15/07/2026
**Percentual total formal do projeto:** **30%**

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
| 4 | Telas essenciais | `[~]` | 0% formal (0% do projeto) | Primeiro bloco do cadastro implementado localmente e em validação; conclusão formal ainda pendente. |
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

A macroetapa 4 está em andamento. O commit Terraform foi transportado para a branch `status4-cadastro`, e o primeiro bloco do cadastro foi implementado localmente. A suíte de testes foi executada com sucesso antes desta rodada de correções.

O cadastro ainda não está concluído formalmente. Permanecem necessárias a validação final, a revisão, o commit, a aplicação controlada futura e a validação pós-deploy.

Subitens previstos, na ordem de execução controlada:

- cadastro completo;
- credenciais AWS;
- credenciais GCP;
- credenciais Azure;
- atualização do próprio plano;
- revisão geral das mensagens de erro e sucesso.

O primeiro bloco do cadastro está implementado localmente, mas ainda não recebeu conclusão formal. Portanto, a macroetapa 4 continua contribuindo com 0% para o percentual formal do projeto.

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
- macroetapa 4 sem entrega funcional concluída = 0%;
- macroetapas 5 a 10 não iniciadas = 0%.

**PERCENTUAL TOTAL FORMAL DO PROJETO: 30%**

Percentuais antigos calculados com versões anteriores do roadmap, incluindo estimativas próximas de 92%, não representam esta sequência oficial de preparação para lançamento e não devem ser reutilizados.

## Próxima ação autorizável

1. Concluir a validação final do primeiro bloco do cadastro.
2. Apresentar testes e diff atualizados para revisão.
3. Criar commit somente após autorização explícita.
4. Planejar a aplicação controlada futura somente após aprovação.
5. Executar validação pós-deploy quando a aplicação for autorizada.

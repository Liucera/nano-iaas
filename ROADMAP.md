# Roadmap — Nano-IaaS

## ✅ Feito

- **CLI multi-cloud** — read, list, config funcionando
- **Provider AWS real** — autenticacao via boto3 confirmada (S3 ListBuckets funcionando)
- **Providers GCP e Azure mock** — dados simulados funcionando
- **Backend FastAPI + JWT** — API REST com autenticacao segura (login, list, audit testados via curl)
- **Tela de login redesenhada** — logo SVG grande de fundo, card translucido, botao com cor solida da logo
- **Logs de auditoria** — filtros, checkboxes, download CSV
- **Deploy na nuvem** — Railway + GitHub Pages com HTTPS
- **Logo + identidade visual** — SVG profissional com 3 clouds
- **Terraform** — provisionamento de infraestrutura (AWS, GCP e Azure completos: main.tf, variables.tf e outputs.tf)
- **Landing page** — apresentacao, precificacao e imagens corrigidas
- **Frontend unificado** — removida versao obsoleta em web/frontend e docs/frontend; docs/index.html e docs/landing.html sao a versao oficial
- **Acessibilidade** — labels do formulario de login associados aos inputs (atributo for/id)

## 🔄 Em andamento

- **Dashboard com paleta dark mode definitiva** — sidebar fixa, busca, timeline de auditoria, paleta de cores especificada (GCP #34A853, Azure #0078D4, AWS #FF9900, fundo #121212/#1E1E1E). Arquivo final gerado, ainda falta aplicar no docs/index.html, testar e commitar.

## 🔜 Falta

- **Providers reais** — GCP e Azure com autenticacao verdadeira (hoje sao mocks)
- **Pagamento PIX manual** — QR code estatico (PNG) + liberacao manual de acesso por email
- **Cadastro de usuarios** — hoje so existe login fixo admin; falta sistema de contas (Free / Pleno / Enterprise)
- **Landing page** — atualizar tabela de precos (Free/Pleno/Enterprise) com novo conteudo e pitch institucional

## Progresso

~99% concluido — falta aplicar o redesign final do dashboard, providers reais de GCP/Azure, e o fluxo de cadastro/pagamento!

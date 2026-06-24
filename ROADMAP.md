# Roadmap — Nano-IaaS

## Concluido (~70%)

- CLI multicloud (read, list, config)
- Provider AWS real (autenticacao via boto3 confirmada, S3 ListBuckets funcionando)
- Providers GCP e Azure mock (dados simulados)
- Backend FastAPI com JWT, CORS restrito e HTTPS
- Tela de login com logo SVG de fundo, sessao persistente (sessionStorage)
- Dashboard redesenhado: sidebar fixa, paleta dark mode, busca por recurso, timeline de auditoria
- Logs de auditoria com download em CSV
- Terraform completo (AWS, GCP e Azure: main.tf, variables.tf, outputs.tf)
- Landing page com planos Gratuito (R$0), Popular (R$100/mes) e Premium (R$1.000/mes), texto revisado em norma culta
- Frontend unificado, sem duplicatas (web/frontend e docs/frontend removidos)

## Pendente antes do lancamento — seguranca e multi-tenant (~20%)

Para lancar no mercado, cada cliente pagante precisa conectar suas PROPRIAS credenciais de nuvem,
isoladas das de outros clientes. Isso exige uma reformulacao de arquitetura, nao apenas ajustes visuais:

- [ ] Banco de dados de usuarios e contas (hoje e so um login fixo "admin" no codigo)
- [ ] Cadastro e autenticacao multiusuario real (Gratuito / Popular / Premium)
- [ ] Armazenamento de credenciais de nuvem por cliente, com criptografia (nunca em texto puro)
- [ ] Token JWT carregando identificacao do usuario, com isolamento de dados por conta
- [ ] Limite de tentativas de login (protecao contra forca bruta)
- [ ] Revisao geral de seguranca antes do lancamento publico

## Outras pendencias (~10%)

- [ ] Providers reais de GCP e Azure (hoje sao mocks; so AWS e real)
- [ ] Pagamento via PIX com QR code estatico e confirmacao manual (modelo inicial, antes de gateway automatizado)

## Progresso geral

~70% concluido. As telas e fluxos visuais estao praticamente prontos, mas o projeto
NAO esta pronto para producao multiusuario: faltam a camada de seguranca e o isolamento
de dados entre clientes (20%), alem dos providers reais restantes e do fluxo de pagamento (10%).
Esses dois blocos sao pre-requisito para qualquer lancamento comercial.

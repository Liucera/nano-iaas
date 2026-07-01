# Roadmap — Nano-IaaS

## Concluido (~80%)

- CLI multicloud (read, list, config)
- Provider AWS real (S3, autenticado via IAM Role da task ECS) — validado em producao
- Providers GCP e Azure mock (dados simulados)
- Backend FastAPI com JWT (chave em Secrets Manager, nao mais fixa no codigo)
- Tela de login com logo SVG de fundo, sessao persistente (sessionStorage)
- Dashboard redesenhado: sidebar fixa, paleta dark mode, busca por recurso, timeline de auditoria
- Logs de auditoria migrados de arquivo para tabela PostgreSQL (audit_log) — validado, gravando corretamente
- Terraform completo: AWS/GCP/Azure (buckets), e nova infraestrutura de producao (VPC, RDS, ECS Fargate, ALB, Secrets Manager, ECR)
- Backend migrado do Railway para AWS ECS Fargate, com banco RDS PostgreSQL real — migracao concluida e testada de ponta a ponta
- Landing page com planos Gratuito (R$0), Popular (R$100/mes) e Premium (R$1.000/mes), texto revisado em norma culta
- Frontend unificado, sem duplicatas
- Codigo de infraestrutura versionado no GitHub (sem segredos expostos, tfstate protegido por .gitignore)

## Pendente antes do lancamento — seguranca e multi-tenant (~15%)

- [ ] Tabela de USUARIOS no banco (hoje so existe um login fixo "admin" no codigo)
- [ ] Cadastro e autenticacao multiusuario real (Gratuito / Popular / Premium)
- [ ] Armazenamento de credenciais de nuvem por cliente, com criptografia
- [ ] Token JWT carregando identificacao do usuario, com isolamento de dados por conta
- [ ] Limite de tentativas de login (protecao contra forca bruta)
- [ ] Restringir a permissao S3 da IAM Role da task (hoje usa Resource "*", mais amplo que o ideal)
- [ ] Configurar HTTPS no Load Balancer (hoje so HTTP; precisa de certificado ACM + dominio proprio)

## Outras pendencias (~5%)

- [ ] Providers reais de GCP e Azure (hoje sao mocks; so AWS e real)
- [ ] Pagamento via PIX com QR code estatico e confirmacao manual

## Progresso geral

~80% concluido. Backend rodando em infraestrutura AWS propria (ECS Fargate + RDS),
testado de ponta a ponta: login, leitura de dados reais do S3 e auditoria persistida
no banco, tudo validado em producao. Falta a camada de multiusuario/multi-tenant
(maior bloco restante) e HTTPS no Load Balancer antes do lancamento comercial.

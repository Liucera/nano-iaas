# Roadmap — Nano-IaaS

## Concluido (~78%)

- CLI multicloud (read, list, config)
- Provider AWS real (boto3, autenticado via IAM Role da task ECS)
- Providers GCP e Azure mock (dados simulados)
- Backend FastAPI com JWT (chave em Secrets Manager, nao mais fixa no codigo)
- Tela de login com logo SVG de fundo, sessao persistente (sessionStorage)
- Dashboard redesenhado: sidebar fixa, paleta dark mode, busca por recurso, timeline de auditoria
- Logs de auditoria migrados de arquivo para tabela PostgreSQL (audit_log)
- Terraform completo: AWS/GCP/Azure (buckets), e nova infraestrutura de producao (VPC, RDS, ECS Fargate, ALB, Secrets Manager, ECR)
- Backend migrado do Railway para AWS ECS Fargate, com banco RDS PostgreSQL real
- Landing page com planos Gratuito (R$0), Popular (R$100/mes) e Premium (R$1.000/mes), texto revisado em norma culta
- Frontend unificado, sem duplicatas

## Pendente antes do lancamento — seguranca e multi-tenant (~15%)

- [ ] Banco de dados de USUARIOS (hoje so existe um login fixo "admin" no codigo; o banco RDS ja existe e tem a tabela audit_log, falta a tabela de usuarios)
- [ ] Cadastro e autenticacao multiusuario real (Gratuito / Popular / Premium)
- [ ] Armazenamento de credenciais de nuvem por cliente, com criptografia (nunca em texto puro)
- [ ] Token JWT carregando identificacao do usuario, com isolamento de dados por conta
- [ ] Limite de tentativas de login (protecao contra forca bruta)
- [ ] Revisar a permissao S3 da IAM Role da task (hoje usa Resource "*", mais ampla que o ideal; restringir aos buckets especificos)
- [ ] Configurar HTTPS no Load Balancer (hoje so HTTP; precisa de certificado ACM + dominio proprio)

## Outras pendencias (~7%)

- [ ] Providers reais de GCP e Azure (hoje sao mocks; so AWS e real)
- [ ] Pagamento via PIX com QR code estatico e confirmacao manual

## Progresso geral

~78% concluido. O backend agora roda em infraestrutura AWS real e propria (ECS Fargate + RDS),
nao depende mais do Railway. Falta a camada de multiusuario/multi-tenant (que e o maior bloco
de trabalho restante) e HTTPS no Load Balancer antes do lancamento comercial.

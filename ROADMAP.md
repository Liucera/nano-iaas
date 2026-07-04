# Roadmap — Nano-IaaS

## Concluido (~92%)

- CLI multicloud (read, list, config)
- Provider AWS real (S3, autenticado via credenciais do usuario ou IAM Role da task) — validado em producao
- Providers GCP e Azure mock (dados simulados)
- Backend FastAPI com JWT (chave em Secrets Manager)
- Sistema MULTIUSUARIO completo: cadastro aberto, login, isolamento de dados por conta — validado de ponta a ponta
- Tabela de usuarios (email, senha hash, plano, is_admin) no RDS PostgreSQL
- Credenciais de nuvem por cliente, criptografadas com Fernet (chave mestra no Secrets Manager)
- Conta admin migrada para o novo sistema, com fallback de credenciais do sistema preservado
- Isolamento de seguranca confirmado: contas novas nao acessam credenciais de outras contas
- Tela de login com logo SVG de fundo, sessao persistente (sessionStorage)
- Dashboard redesenhado: sidebar fixa, paleta dark mode, busca por recurso, timeline de auditoria
- Logs de auditoria em tabela PostgreSQL (audit_log)
- Terraform completo: VPC, RDS, ECS Fargate, ALB, Secrets Manager (JWT + criptografia), ECR
- Backend rodando em AWS propria (ECS Fargate + RDS), sem depender de Railway
- Landing page com planos Gratuito (R$0), Popular (R$100/mes) e Premium (R$1.000/mes)
- Frontend unificado, codigo versionado no GitHub sem segredos expostos

## Pendente antes do lancamento (~5%)

- [ ] Limite de tentativas de login (protecao contra forca bruta)
- [ ] Restringir a permissao S3 da IAM Role da task (hoje usa Resource "*", mais amplo que o ideal)
- [ ] Configurar HTTPS no Load Balancer (hoje so HTTP; precisa de certificado ACM + dominio proprio)
- [ ] Frontend: telas de cadastro e de configuracao de credenciais de nuvem (hoje so existem via API/curl)
- [ ] Rota para o usuario ATUALIZAR seu proprio plano

## Outras pendencias (~3%)

- [ ] Providers reais de GCP e Azure (hoje sao mocks; so AWS e real)
- [ ] Pagamento via PIX com QR code estatico e confirmacao manual

## Progresso geral

~92% concluido. O bloco mais critico e complexo do projeto — o sistema multiusuario
com credenciais criptografadas e isolamento de dados por conta — esta implementado,
testado e validado em producao. Falta principalmente a interface visual (frontend)
para cadastro/credenciais, HTTPS, e alguns refinamentos de seguranca antes do
lancamento comercial.

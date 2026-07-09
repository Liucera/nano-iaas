# Roadmap — Nano-IaaS

## Status atual - Beta QA (~99% do MVP)

- CLI multicloud (read, list, config; AWS real, GCP/Azure ainda mock/dev)
- Provider AWS real (S3, autenticado via credenciais do usuário ou IAM Role da task) — validado em produção
- Provider GCP real no Dashboard/API (Google Cloud Storage via service account JSON)
- Provider Azure real no Dashboard/API (Blob Storage via connection string)
- Backend FastAPI com JWT (chave em Secrets Manager)
- Sistema MULTIUSUARIO completo: cadastro aberto, login, isolamento de dados por conta — validado de ponta a ponta
- Tabela de usuarios (email, senha hash, plano, is_admin) no RDS PostgreSQL
- Credenciais de nuvem por cliente, criptografadas com Fernet (chave mestra no Secrets Manager)
- Conta admin migrada para o novo sistema, com fallback de credenciais do sistema preservado
- Isolamento de seguranca confirmado: contas novas nao acessam credenciais de outras contas
- Tela de login com logo SVG de fundo, sessao persistente (sessionStorage)
- Dashboard redesenhado: sidebar fixa, paleta dark mode, busca por recurso, timeline de auditoria
- Logs de auditoria em tabela PostgreSQL (audit_log)
- Terraform completo: VPC, RDS, ECS Fargate, ALB, Secrets Manager (JWT + criptografia), ECR, ACM para dominio da API
- Backend rodando em AWS propria (ECS Fargate + RDS), sem depender de Railway
- Landing page com planos Gratuito (R$0), Popular (R$100/mes) e Premium (R$1.000/mes)
- Frontend unificado, cadastro e configuracao basica de credenciais/plano
- Testes automatizados locais passando
- Pagamento Pix manual com chave configuravel por ambiente
- Dominio proprio definido: app.nano-iaas.com.br e api.nano-iaas.com.br
- Política read-only mantida: apenas listagem e leitura; sem escrita, delete ou alteração de recursos
- Tutorial Beta multi-cloud definido para AWS S3, Azure Blob Storage e Google Cloud Storage
- Posicionamento oficial: camada web multiusuário, segura e auditável; não substitui AWS/Azure/GCP
- Frente Pré-Beta de LGPD e Privacidade criada com documentos iniciais

## Pendente antes do lancamento (~5%)

- [x] Limite de tentativas de login (protecao contra forca bruta)
- [ ] Revisão jurídica futura da Política de Privacidade e Termos de Uso
- [ ] Restringir a permissao S3 da IAM Role da task (hoje usa Resource "*", mais amplo que o ideal)
- [x] Preparar certificado ACM e listener HTTPS no Terraform
- [ ] Criar registros DNS no Registro.br e validar o certificado ACM
- [x] Documentos iniciais de Privacidade e Termos de Uso para adequação inicial à LGPD
- [x] Frontend: cadastro e configuracao basica de credenciais de nuvem sem depender de API/curl
- [x] Rota para o usuario ATUALIZAR seu proprio plano

## Outras pendencias (~3%)

- [x] Pagamento via Pix estatico/manual com solicitacao de aprovacao

## Progresso geral

~99% do MVP concluido. O projeto esta pronto para iniciar QA/Beta controlado. Falta principalmente criar/validar os registros DNS no Registro.br, ativar o listener HTTPS depois que o ACM emitir o certificado, endurecer a permissao S3 da IAM Role e validar operacionalmente com credenciais reais nas tres nuvens.

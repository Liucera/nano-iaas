# Roadmap — Nano-IaaS

## Status atual - Beta QA (~99% do MVP)

- CLI multicloud (read, list, config; AWS real, GCP/Azure ainda mock/dev)
- Provider AWS real (S3, autenticado via credenciais do usuário ou IAM Role da task) — validado em produção
- Provider GCP real no Dashboard/API (Google Cloud Storage via service account JSON)
- Provider Azure real no Dashboard/API (Blob Storage via connection string)
- Backend FastAPI com JWT (chave em Secrets Manager)
- Sistema MULTIUSUARIO completo: cadastro aberto, login, isolamento de dados por conta — validado de ponta a ponta
- Tabela de usuários (email, senha hash, plano, is_admin) no RDS PostgreSQL
- Credenciais de nuvem por cliente, criptografadas com Fernet (chave mestra no Secrets Manager)
- Conta admin migrada para o novo sistema, com fallback de credenciais do sistema preservado
- Isolamento de segurança confirmado: contas novas não acessam credenciais de outras contas
- Tela de login com logo SVG de fundo, sessão persistente (sessionStorage)
- Dashboard redesenhado: sidebar fixa, paleta dark mode, busca por recurso, timeline de auditoria
- Logs de auditoria em tabela PostgreSQL (audit_log)
- Terraform completo: VPC, RDS, ECS Fargate, ALB, Secrets Manager (JWT + criptografia), ECR, ACM para domínio da API
- Backend rodando em AWS própria (ECS Fargate + RDS), sem depender de Railway
- Landing page com planos Gratuito (R$0), Popular (R$100/mês) e Premium (R$1.000/mês)
- Frontend unificado, cadastro e configuração básica de credenciais/plano
- Testes automatizados locais passando
- Pagamento Pix manual com chave configurável por ambiente
- Domínio próprio definido: app.nano-iaas.com.br e api.nano-iaas.com.br
- API pública protegida por HTTPS com certificado ACM emitido e validado; listener HTTP 80 redirecionando para HTTPS 443 e listener HTTPS encaminhando para o target group da API
- Endpoint `/docs` validado com HTTP 200; a rota `/` retorna 404 por não existir, sem indicar falha de infraestrutura
- Política read-only mantida: apenas listagem e leitura; sem escrita, delete ou alteração de recursos
- Tutorial Beta multi-cloud definido para AWS S3, Azure Blob Storage e Google Cloud Storage
- Posicionamento oficial: camada web multiusuário, segura e auditável; não substitui AWS/Azure/GCP
- Frente Pré-Beta de LGPD e Privacidade criada com documentos iniciais

## Pendente antes do lançamento (~5%)

- [x] Limite de tentativas de login (proteção contra força bruta)
- [x] Adicionar checkbox de aceite dos Termos de Uso e Política de Privacidade no cadastro
- [ ] Revisão jurídica futura da Política de Privacidade e Termos de Uso
- [ ] Teste operacional real com credenciais Azure
- [ ] Teste operacional real com credenciais GCP
- [ ] Resolver ou documentar oficialmente o CLI parcial (AWS real; GCP/Azure mock/dev)
- [x] Criar registros DNS no Registro.br e validar o certificado ACM/HTTPS
- [ ] Restringir a permissão S3 da IAM Role da task (hoje usa Resource "*", mais amplo que o ideal)
- [x] Preparar certificado ACM e listener HTTPS no Terraform
- [x] Persistir aceite de termos no cadastro (aceite_termos, versao_termos e data_aceite_termos)
- [x] Documentos iniciais de Privacidade e Termos de Uso para adequação inicial à LGPD
- [x] Tutorial oficial da Beta com três caminhos: AWS S3, Azure Blob Storage e Google Cloud Storage
- [x] Frontend: cadastro e configuração básica de credenciais de nuvem sem depender de API/curl
- [x] Rota para o usuário ATUALIZAR seu próprio plano

## Outras pendências (~3%)

- [x] Pagamento via Pix estático/manual com solicitação de aprovação

## Progresso geral

~99% do MVP concluído. O projeto está pronto para iniciar QA/Beta controlado. DNS, certificado ACM e listeners HTTPS da API estão ativos e validados. Falta principalmente validar operacionalmente Azure e GCP com credenciais reais, resolver/documentar o CLI parcial e endurecer a permissão S3 da IAM Role.

<div align="center">
  <img src="./docs/logo.svg" alt="Nano-IaaS" width="400"/>
  
  # Nano-IaaS
  
  **Dashboard multi-cloud para leitura e auditoria de dados**
  
  [![API](https://img.shields.io/badge/api-api.nano--iaas.com.br-orange)](https://api.nano-iaas.com.br/docs)
  [![Frontend](https://img.shields.io/badge/app-app.nano--iaas.com.br-222)](https://app.nano-iaas.com.br/)
  [![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688)](https://fastapi.tiangolo.com)
  [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

  [Acessar Dashboard](https://app.nano-iaas.com.br/) | [API Docs](https://api.nano-iaas.com.br/docs)
</div>

---


## Status Beta

MVP em fase Beta/QA. O projeto usa frontend no GitHub Pages com domínio próprio e backend em AWS ECS Fargate + ALB. O certificado HTTPS da API é emitido pelo AWS ACM e validado por DNS no Registro.br.

### Estado oficial em 23/07/2026

- Macroetapas 1, 2 e 3: concluídas;
- Macroetapa 4 — Telas essenciais: concluída, com seis dos seis blocos formalmente encerrados (100%);
- Cadastro `[x]`;
- Credenciais AWS `[x]`;
- Credenciais GCP `[x]`;
- Credenciais Azure `[x]`;
- Atualização do próprio plano `[x]`, concluída dentro das regras comerciais e dos mecanismos de autorização já existentes;
- Revisão geral das mensagens de erro e sucesso `[x]`, implantada e validada em produção;
- validação real das credenciais contra AWS, GCP ou Azure: reservada para a Macroetapa 6.

A referência operacional vigente é a `main` no commit `07d111bd9122cc55b6b54756c2be2337eaf1a0f1`. O frontend publicado corresponde a essa revisão. O backend está implantado na task definition ECS `nano-iaas-backend-dev:12`, usando a imagem imutável `nano-iaas-backend-dev@sha256:51852fd81212d6c2c143d18d703492167d30dd6f3b2af31404999d922c8a047e`.

### Planos e fluxo comercial vigente

- planos permitidos pelo servidor: `gratuito`, `popular` e `premium`;
- valores já versionados: Gratuito R$ 0, Popular R$ 100 e Premium R$ 1.000;
- o próprio usuário pode manter o plano atual ou mudar diretamente para o Gratuito;
- Popular e Premium exigem solicitação PIX com valor definido pelo servidor e aprovação administrativa manual;
- criar uma solicitação não ativa o plano pago; a alteração ocorre somente após aprovação válida da solicitação pendente;
- este bloco não adiciona gateway, nova cobrança, novo plano, novo preço ou ativação paga automática.

### Validação formal da atualização do próprio plano

Em 21/07/2026, o fluxo implantado foi validado de forma autenticada e somente leitura com uma conta comum, sem privilégios administrativos:

- `GET /me` e `GET /me/plano/opcoes` responderam HTTP 200;
- a resposta identificou corretamente o usuário comum e retornou os três planos permitidos, com valores numéricos e modos de ativação;
- o plano atual foi identificado na resposta e permanece filtrado pelo frontend ao apresentar alternativas;
- nenhum token, senha, comprovante, credencial cloud ou outro segredo foi exposto;
- nenhum plano, solicitação PIX ou dado persistente foi alterado durante a validação.

### Revisão geral das mensagens

A implementação do Bloco 4.6 padroniza mensagens públicas e fallbacks para respostas HTTP 400, 401, 403, 404, 409, 422, 429, 500 e 502, preserva `Retry-After`, trata falhas de conexão em português e impede a exposição literal de erros operacionais desconhecidos. As regiões de status anunciam erros de forma acessível e direcionam o foco para o estado principal quando necessário. O frontend preserva compatibilidade temporária com respostas antigas sem acentuação.

A validação aprovou 256 testes, incluindo testes comportamentais Node sem rede real. A imagem Alpine oficial foi fixada por digest, validada como `linux/amd64` e publicada no ECR; o scan ECR do manifest executável foi concluído sem findings. O Docker Scout registrou apenas o HIGH CVE-2024-23342 em `ecdsa 0.19.2`, documentado como não alcançável pelo fluxo atual porque o backend restringe criação e validação de tokens a `HS256`.

Em produção, o serviço ECS alcançou estado estável com uma tarefa em execução, nenhum pending e target saudável no ALB. Os smoke tests confirmaram documentação e OpenAPI em HTTP 200, autenticação de usuário comum, `GET /me`, opções de plano, bloqueio HTTP 403 de auditoria para não administradores, validação HTTP 422 antes de persistência e ausência de segredos nas respostas. Nenhum plano, PIX ou dado persistente foi alterado.

### Repositórios oficiais e responsabilidades

O projeto possui dois repositórios com responsabilidades separadas:

| Repositório | Responsabilidade |
|---|---|
| [`Liucera/nano-iaas`](https://github.com/Liucera/nano-iaas) | Fonte oficial do produto: backend, frontend autenticado em `docs/`, CLI, providers, testes, infraestrutura Terraform e fluxo de build/deploy do backend. O frontend legado do aplicativo é publicado a partir de `main:/docs` em <https://app.nano-iaas.com.br>. |
| [`Liucera/Liucera.github.io`](https://github.com/Liucera/Liucera.github.io) | Fonte oficial do site institucional do Nano-IaaS, publicado no domínio principal <https://nano-iaas.com.br> pelo Cloudflare Pages. |

Alterações dos dois repositórios não podem ser misturadas em uma mesma branch, commit, PR ou operação de deploy. Código, infraestrutura e deploy do aplicativo/API pertencem exclusivamente ao `Liucera/nano-iaas`; o `Liucera/Liucera.github.io` permanece restrito ao site institucional.

Domínios planejados:
- Dashboard: https://app.nano-iaas.com.br
- API Docs: https://api.nano-iaas.com.br/docs

Registros DNS necessários no Registro.br:
- `app.nano-iaas.com.br` como CNAME para `Liucera.github.io`.
- `api.nano-iaas.com.br` como CNAME para o DNS do ALB retornado em `terraform/aws-infra` pelo output `alb_dns_name`.
- CNAME de validação do ACM retornado pelo output `acm_dns_validation_records` após `terraform apply`.

Para ativar HTTPS no ALB depois que o ACM estiver validado:

```bash
cd terraform/aws-infra
terraform apply -var="enable_https=true"
```

---

## O que é o Nano-IaaS?

O **Nano-IaaS** conecta **AWS S3**, **Azure Blob Storage** e **Google Cloud Storage** em um painel único, seguro, auditável e somente leitura.

> Read-only by design - nenhuma operação de escrita ou deleção e permitida.

---

## Posicionamento

O Nano-IaaS não é uma substituição para AWS, Azure ou Google Cloud.

A proposta do projeto é oferecer uma camada web, multiusuário, segura e auditável para leitura de dados em ambientes cloud.

A plataforma atua em modo read-only, permitindo listagem e leitura de recursos sem operações de escrita, alteração ou exclusão.

Na Beta, o Dashboard/API usa providers reais para AWS S3 (`boto3`), Azure Blob Storage (`azure-storage-blob`) e Google Cloud Storage (`google-cloud-storage`). O CLI usa AWS real, enquanto GCP e Azure ainda estão em modo mock/dev.

---

## Status dos providers

| Superfície | AWS | GCP | Azure |
|---|---|---|---|
| Dashboard/API | Real via `boto3` | Real via `google-cloud-storage` | Real via `azure-storage-blob` |
| CLI | Real via `boto3` | Mock/dev | Mock/dev |

O Dashboard/API está conectado aos providers reais para AWS S3, Azure Blob Storage e Google Cloud Storage. O CLI ainda é parcial: AWS usa o provider real, enquanto GCP e Azure continuam apontando para mocks de desenvolvimento.

Observação técnica interna da Beta: o Dashboard/API é multi-cloud real. O CLI ainda está em consolidação para GCP e Azure.

A promessa de segurança permanece read-only: os providers devem apenas listar recursos e ler objetos/blobs. Não há operações de escrita, deleção ou alteração de recursos nas nuvens.

---

## Funcionalidades

- Multi-cloud - AWS, GCP e Azure em uma interface só
- Autenticação JWT - login seguro com token de acesso
- Dashboard visual - visualização de buckets e containers
- Leitura de dados - suporte a JSON, JSONL, CSV e LOG
- Auditoria completa - registro de quem acessou o que e quando
- HTTPS - comunicação criptografada de ponta a ponta
- Deploy na nuvem - AWS ECS Fargate + ALB (backend) + GitHub Pages (frontend)

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Autenticação | JWT (python-jose + passlib) |
| CLI | Click + Rich |
| AWS | boto3 |
| GCP | google-cloud-storage |
| Azure | azure-storage-blob |
| Frontend | HTML + CSS + JavaScript |
| Deploy Backend | AWS ECS Fargate + ALB |
| Deploy Frontend | GitHub Pages |
| CI/CD | GitHub Actions |

---

## Privacidade e LGPD

O Nano-IaaS possui uma frente Pré-Beta de privacidade e proteção de dados, tratada como adequação inicial à LGPD.

Documentos iniciais:
- [Política de Privacidade](docs/PRIVACIDADE.md)
- [Termos de Uso](docs/TERMOS_DE_USO.md)

Pontos principais:
- O produto atua em modo read-only: apenas listagem e leitura de recursos cloud.
- O usuário deve fornecer credenciais cloud com permissões mínimas e somente leitura.
- Credenciais cloud cadastradas são armazenadas criptografadas.
- Logs de auditoria podem ser gerados para segurança e rastreabilidade.
- A tela de cadastro exige aceite explícito dos Termos de Uso e da Política de Privacidade.
- O contrato de `POST /cadastro` exige `full_name`, e-mail, senha, plano solicitado, aceites separados (`aceite_termos` e `aceite_privacidade`) e as versões legais `terms_version` e `privacy_version`, ambas em `2026-07-15`. Todo cadastro público inicia no plano `gratuito` e sem privilégios administrativos.
- Temporariamente, o backend também aceita o contrato legado com `versao_termos=beta-2026-07`; o contrato novo acima permanece oficial, e a compatibilidade será removida após a estabilização do frontend novo.
- `GET /me` retorna `full_name` (nulo para contas antigas), `email`, `plano`, `is_admin` e `providers_configurados`. Clientes devem usar o e-mail como fallback quando `full_name` for nulo.

Esta documentação não promete conformidade total com a LGPD; ela representa uma adequação inicial que deve passar por revisão jurídica futura.

---

## Tutorial Beta multi-cloud

O tutorial oficial da Beta tem três caminhos, todos seguindo o mesmo fluxo operacional:

| Caminho | Provider | Credencial esperada |
|---|---|---|
| Conectar AWS S3 | AWS S3 | Access key ID e secret access key, variáveis AWS ou IAM Role |
| Conectar Azure Blob Storage | Azure Blob Storage | Connection string |
| Conectar Google Cloud Storage | Google Cloud Storage | Service account JSON |

Fluxo comum para os três providers:

1. Criar conta.
2. Fazer login.
3. Cadastrar credenciais.
4. Escolher provider.
5. Listar buckets/containers.
6. Abrir arquivos.
7. Consultar auditoria.

Durante a Beta, esse fluxo oficial vale para o Dashboard/API. O CLI segue disponível, mas GCP e Azure ainda estão em consolidação no CLI e podem usar mocks/dev.

---

## Como rodar localmente

### Pre-requisitos
- Python 3.12+
- Git
- WSL2 (recomendado no Windows)

### Instalação

```bash
git clone https://github.com/Liucera/nano-iaas.git
cd nano-iaas
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Rodando o backend

```bash
uvicorn web.backend.main:app --reload
```

### Rodando o frontend

```bash
python3 -m http.server 3000 --directory docs
```

Acesse: http://localhost:3000

Credenciais padrao:
- Usuario: admin
- Senha: definida pelo administrador

---

## CLI

```bash
nano-iaas list gcp
nano-iaas list azure
nano-iaas list aws
nano-iaas read gs://nano-iaas-dev/dados/
nano-iaas config set
```

---

## Autor

Arlindo Barroso - Estudante de Provisionamento de Servicos Computacionais (CLOUD) pelo CAPACITA IREDE

GitHub: https://github.com/Liucera

---

## Licença

Este projeto está sob a licença MIT.

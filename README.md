<div align="center">
  <img src="nanoiaasmage.png" alt="Nano-IaaS" width="120"/>
  
  # Nano-IaaS
  
  **Dashboard multi-cloud para leitura e auditoria de dados**
  
  [![Deploy](https://img.shields.io/badge/backend-railway-blueviolet)](https://web-production-87d4d.up.railway.app)
  [![Frontend](https://img.shields.io/badge/frontend-github%20pages-222)](https://liucera.github.io/nano-iaas/)
  [![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688)](https://fastapi.tiangolo.com)
  [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

  [Acessar Dashboard](https://liucera.github.io/nano-iaas/) | [API Docs](https://web-production-87d4d.up.railway.app/docs)
</div>

---

## O que e o Nano-IaaS?

O **Nano-IaaS** e uma plataforma web de leitura e auditoria de dados multi-cloud. Permite que equipes acessem dados armazenados em **AWS S3**, **Google Cloud Storage** e **Azure Blob Storage** em uma unica interface segura, sem precisar de acesso direto as clouds.

> Read-only by design - nenhuma operacao de escrita ou delecao e permitida.

---

## Funcionalidades

- Multi-cloud - AWS, GCP e Azure em uma interface so
- Autenticacao JWT - login seguro com token de acesso
- Dashboard visual - visualizacao de buckets e containers
- Leitura de dados - suporte a JSON, JSONL, CSV e LOG
- Auditoria completa - registro de quem acessou o que e quando
- HTTPS - comunicacao criptografada de ponta a ponta
- Deploy na nuvem - Railway (backend) + GitHub Pages (frontend)

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Autenticacao | JWT (python-jose + passlib) |
| CLI | Click + Rich |
| AWS | boto3 |
| GCP | google-cloud-storage |
| Azure | azure-storage-blob |
| Frontend | HTML + CSS + JavaScript |
| Deploy Backend | Railway |
| Deploy Frontend | GitHub Pages |
| CI/CD | GitHub Actions |

---

## Como rodar localmente

### Pre-requisitos
- Python 3.12+
- Git
- WSL2 (recomendado no Windows)

### Instalacao

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
python3 -m http.server 3000 --directory web/frontend
```

Acesse: http://localhost:3000

Credenciais padrao:
- Usuario: admin
- Senha: Nano@2026

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

## Roadmap

- [x] CLI multi-cloud
- [x] Providers GCP, Azure e AWS mock
- [x] Backend FastAPI com JWT
- [x] Dashboard web
- [x] Logs de auditoria
- [x] Deploy na nuvem (Railway + GitHub Pages)
- [ ] Providers reais (GCP e Azure)
- [ ] Landing page
- [ ] Multiplos usuarios com niveis de acesso

---

## Autor

Arlindo Barroso - Estudante de Provisionamento de Servicos Computacionais (CLOUD) pelo CAPACITA IREDE

GitHub: https://github.com/Liucera

---

## Licenca

Este projeto esta sob a licenca MIT.

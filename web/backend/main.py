import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from providers.gcp.gcs_reader_mock import GCSReaderMock
from providers.azure.blob_reader_mock import BlobReaderMock
from providers.aws.s3_reader_mock import S3ReaderMock

# ── Configurações de segurança ──────────────────────────────
SECRET_KEY = "nano-iaas-chave-secreta-2026"
ALGORITHM = "HS256"
TOKEN_EXPIRA_EM = 60  # minutos

# ── Usuários permitidos (em produção ficaria no banco de dados) ──
USUARIOS = {
    "admin": {
        "usuario": "admin",
        "senha_hash": "$2b$12$WaYNM9scCxLtUwGssOajgODRKXA08BIEZHAH/3Efj9GxSgfdIepJm"
    }
}

# ── Ferramentas de segurança ────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI(title="Nano-IaaS Web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Token(BaseModel):
    access_token: str
    token_type: str

# ── Funções de autenticação ─────────────────────────────────
def verificar_senha(senha_plana, senha_hash):
    return pwd_context.verify(senha_plana, senha_hash)

def criar_token(dados: dict):
    copia = dados.copy()
    expira = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRA_EM)
    copia.update({"exp": expira})
    return jwt.encode(copia, SECRET_KEY, algorithm=ALGORITHM)

def usuario_atual(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario = payload.get("sub")
        if usuario is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        return usuario
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ── Rotas ───────────────────────────────────────────────────
@app.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    usuario = USUARIOS.get(form.username)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    if not verificar_senha(form.password, usuario["senha_hash"]):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    token = criar_token({"sub": form.username})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/list/{provider}")
def list_resources(provider: str, usuario: str = Depends(usuario_atual)):
    try:
        if provider == "gcp":
            p = GCSReaderMock()
            p.authenticate({})
        elif provider == "azure":
            p = BlobReaderMock()
            p.authenticate({})
        elif provider == "aws":
            p = S3ReaderMock()
            p.authenticate({})
        else:
            return {"error": "Provider não encontrado"}

        resources = list(p.list_resources())
        return {"provider": provider, "resources": resources}
    except Exception as e:
        return {"error": str(e)}

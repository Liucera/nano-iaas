import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import boto3
import psycopg2
import psycopg2.extras

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from providers.gcp.gcs_reader_mock import GCSReaderMock
from providers.azure.blob_reader_mock import BlobReaderMock
from providers.aws.s3_reader import S3Reader

# ── Configuracoes de seguranca ──────────────────────────────
# A SECRET_KEY NUNCA fica fixa no codigo. Deve vir de variavel de ambiente,
# configurada no App Runner / Railway / ambiente local (.env, fora do Git).
SECRET_KEY = os.environ.get("NANO_IAAS_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "NANO_IAAS_SECRET_KEY nao configurada. Defina essa variavel de ambiente "
        "antes de iniciar o servidor (nunca use uma chave fixa em produção)."
    )

ALGORITHM = "HS256"
TOKEN_EXPIRA_EM = 60  # minutos

# ── Conexao com o banco de dados (credenciais via Secrets Manager) ──
def obter_credenciais_db():
    """
    Le as credenciais do banco a partir da variavel de ambiente DATABASE_SECRET_ARN
    (populada pelo App Runner a partir do AWS Secrets Manager), ou, em ambiente local
    de desenvolvimento, a partir de variaveis DB_* individuais.
    """
    secret_arn = os.environ.get("DATABASE_SECRET_ARN")
    if secret_arn:
        client = boto3.client("secretsmanager")
        resposta = client.get_secret_value(SecretId=secret_arn)
        return json.loads(resposta["SecretString"])

    # Fallback para desenvolvimento local
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", 5432)),
        "dbname": os.environ.get("DB_NAME", "nano_iaas"),
        "username": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", ""),
    }

def conectar_db():
    cred = obter_credenciais_db()
    return psycopg2.connect(
        host=cred["host"],
        port=cred["port"],
        dbname=cred["dbname"],
        user=cred["username"],
        password=cred["password"],
    )

def garantir_tabela_auditoria():
    """Cria a tabela de auditoria se ainda nao existir. Chamado uma vez ao iniciar o app."""
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
                    usuario TEXT NOT NULL,
                    acao TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    recurso TEXT,
                    detalhes TEXT
                );
            """)
        conn.commit()
    finally:
        conn.close()

def registrar_acesso(usuario: str, acao: str, provider: str, recurso: str, detalhes: str = ""):
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider, recurso, detalhes)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (usuario, acao, provider, recurso, detalhes),
            )
        conn.commit()
    finally:
        conn.close()

def buscar_logs_auditoria(limite: int = 50):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT timestamp, usuario, acao, provider, recurso, detalhes
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (limite,),
            )
            linhas = cur.fetchall()
        logs = []
        for linha in linhas:
            logs.append({
                "timestamp": linha["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                "usuario": linha["usuario"],
                "acao": linha["acao"],
                "provider": linha["provider"],
                "recurso": linha["recurso"] or "-",
                "detalhes": linha["detalhes"] or "",
            })
        return logs
    finally:
        conn.close()

# ── Usuarios permitidos (em produção, virá de uma tabela de usuários no banco) ──
USUARIOS = {
    "admin": {
        "usuario": "admin",
        "senha_hash": "$2b$12$iFhBXzXNqhksnzFyE5Zky.21nIufhCyBaX9OzOqMD99BrJyhyxaxi"
    }
}

# ── Ferramentas de seguranca ────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI(title="Nano-IaaS Web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://liucera.github.io"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def ao_iniciar():
    garantir_tabela_auditoria()

class Token(BaseModel):
    access_token: str
    token_type: str

# ── Funcoes de autenticacao ─────────────────────────────────
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
            p = S3Reader()
            p.authenticate({'mode': 'env'})
        else:
            return {"error": "Provider não encontrado"}

        resources = list(p.list_resources())
        registrar_acesso(usuario, "LIST", provider, "-", f"{len(resources)} recursos")
        return {"provider": provider, "resources": resources}
    except Exception as e:
        return {"error": str(e)}

@app.get("/read/{provider}/{bucket}")
def read_resource(provider: str, bucket: str, usuario: str = Depends(usuario_atual)):
    try:
        if provider == "gcp":
            p = GCSReaderMock()
        elif provider == "azure":
            p = BlobReaderMock()
        elif provider == "aws":
            p = S3Reader()
            p.authenticate({'mode': 'env'})
        else:
            return {"error": "Provider não encontrado"}

        prefix = f"gs://{bucket}/dados/" if provider == "gcp" else \
                 f"azure://{bucket}/dados/" if provider == "azure" else \
                 f"s3://{bucket}/"

        records = list(p.read(prefix))
        registrar_acesso(usuario, "READ", provider, bucket, f"{len(records)} registros")
        return {"provider": provider, "bucket": bucket, "records": records}
    except Exception as e:
        return {"error": str(e)}

@app.get("/audit")
def ver_logs(usuario: str = Depends(usuario_atual)):
    try:
        logs = buscar_logs_auditoria(limite=50)
        return {"logs": logs}
    except Exception as e:
        return {"logs": [], "error": str(e)}

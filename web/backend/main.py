import sys
import os
import json
from collections import defaultdict, deque
from time import monotonic
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import boto3
import psycopg2
import psycopg2.extras
from botocore.exceptions import ClientError
from azure.core.exceptions import AzureError

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from cryptography.fernet import Fernet

from google.api_core.exceptions import GoogleAPIError
from providers.gcp.gcs_reader import GCSReader
from providers.azure.blob_reader import BlobReader
from providers.aws.s3_reader import S3Reader

# ── Configuracoes de seguranca ──────────────────────────────
SECRET_KEY = os.environ.get("NANO_IAAS_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "NANO_IAAS_SECRET_KEY nao configurada. Defina essa variavel de ambiente "
        "antes de iniciar o servidor (nunca use uma chave fixa em produção)."
    )

ALGORITHM = "HS256"
TOKEN_EXPIRA_EM = 60  # minutos

PLANOS_VALIDOS = ("gratuito", "popular", "premium")
PROVIDERS_VALIDOS = ("gcp", "azure", "aws")
LOGIN_MAX_TENTATIVAS = 5
LOGIN_JANELA_SEGUNDOS = 300
_tentativas_login = defaultdict(deque)

# ── Chave de criptografia das credenciais de nuvem dos clientes ──
def obter_chave_criptografia():
    secret_arn = os.environ.get("NANO_IAAS_ENCRYPTION_KEY_ARN")
    if secret_arn:
        client = boto3.client("secretsmanager")
        resposta = client.get_secret_value(SecretId=secret_arn)
        valor = resposta["SecretString"]
        return _normalizar_chave_fernet(valor)

    valor_local = os.environ.get("NANO_IAAS_ENCRYPTION_KEY")
    if valor_local:
        return _normalizar_chave_fernet(valor_local)

    raise RuntimeError(
        "Nenhuma chave de criptografia configurada (NANO_IAAS_ENCRYPTION_KEY_ARN "
        "ou NANO_IAAS_ENCRYPTION_KEY)."
    )

def _normalizar_chave_fernet(valor: str) -> bytes:
    import base64
    bruto = base64.b64decode(valor) if _parece_base64_padrao(valor) else valor.encode()
    if len(bruto) != 32:
        import hashlib
        bruto = hashlib.sha256(bruto).digest()
    return base64.urlsafe_b64encode(bruto)

def _parece_base64_padrao(valor: str) -> bool:
    import base64
    try:
        base64.b64decode(valor, validate=True)
        return True
    except Exception:
        return False

_fernet = None

def obter_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(obter_chave_criptografia())
    return _fernet

def criptografar(texto_plano: str) -> str:
    return obter_fernet().encrypt(texto_plano.encode()).decode()

def descriptografar(texto_cifrado: str) -> str:
    return obter_fernet().decrypt(texto_cifrado.encode()).decode()

# ── Conexao com o banco de dados (credenciais via Secrets Manager) ──
def obter_credenciais_db():
    secret_arn = os.environ.get("DATABASE_SECRET_ARN")
    if secret_arn:
        client = boto3.client("secretsmanager")
        resposta = client.get_secret_value(SecretId=secret_arn)
        return json.loads(resposta["SecretString"])

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

def garantir_tabelas():
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    senha_hash TEXT NOT NULL,
                    plano TEXT NOT NULL DEFAULT 'gratuito',
                    is_admin BOOLEAN NOT NULL DEFAULT false,
                    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cloud_credentials (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    credencial_cifrada TEXT NOT NULL,
                    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE(user_id, provider)
                );
            """)
        conn.commit()
    finally:
        conn.close()

def migrar_admin_inicial():
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE is_admin = true LIMIT 1;")
            if cur.fetchone():
                return
            cur.execute(
                """
                INSERT INTO users (email, senha_hash, plano, is_admin)
                VALUES (%s, %s, 'premium', true)
                ON CONFLICT (email) DO NOTHING
                """,
                ("admin@nano-iaas.com", "$2b$12$iFhBXzXNqhksnzFyE5Zky.21nIufhCyBaX9OzOqMD99BrJyhyxaxi"),
            )
        conn.commit()
    finally:
        conn.close()

# ── Funcoes de acesso a usuarios ─────────────────────────────
def buscar_usuario_por_email(email: str):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, senha_hash, plano, is_admin FROM users WHERE email = %s",
                (email,),
            )
            return cur.fetchone()
    finally:
        conn.close()

def buscar_usuario_por_id(user_id: int):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, plano, is_admin FROM users WHERE id = %s",
                (user_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()

def criar_usuario(email: str, senha_hash: str, plano: str = "gratuito"):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO users (email, senha_hash, plano)
                VALUES (%s, %s, %s)
                RETURNING id, email, plano, is_admin
                """,
                (email, senha_hash, plano),
            )
            novo = cur.fetchone()
        conn.commit()
        return novo
    finally:
        conn.close()

def atualizar_plano_usuario(user_id: int, plano: str):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE users
                SET plano = %s
                WHERE id = %s
                RETURNING id, email, plano, is_admin
                """,
                (plano, user_id),
            )
            usuario = cur.fetchone()
        conn.commit()
        return usuario
    finally:
        conn.close()

# ── Funcoes de acesso a credenciais de nuvem ─────────────────
def salvar_credencial(user_id: int, provider: str, credencial_json: dict):
    cifrado = criptografar(json.dumps(credencial_json))
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cloud_credentials (user_id, provider, credencial_cifrada)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, provider)
                DO UPDATE SET credencial_cifrada = EXCLUDED.credencial_cifrada, criado_em = now()
                """,
                (user_id, provider, cifrado),
            )
        conn.commit()
    finally:
        conn.close()

def buscar_credencial(user_id: int, provider: str):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT credencial_cifrada FROM cloud_credentials WHERE user_id = %s AND provider = %s",
                (user_id, provider),
            )
            linha = cur.fetchone()
        if not linha:
            return None
        return json.loads(descriptografar(linha["credencial_cifrada"]))
    finally:
        conn.close()

def listar_providers_configurados(user_id: int):
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT provider FROM cloud_credentials WHERE user_id = %s",
                (user_id,),
            )
            return [linha[0] for linha in cur.fetchall()]
    finally:
        conn.close()

# ── Auditoria ─────────────────────────────────────────────────
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
    garantir_tabelas()
    migrar_admin_inicial()

class Token(BaseModel):
    access_token: str
    token_type: str

class CadastroRequest(BaseModel):
    email: EmailStr
    senha: str
    plano: str = "gratuito"

class PlanoRequest(BaseModel):
    plano: str

class CredencialAWS(BaseModel):
    access_key_id: str
    secret_access_key: str

class CredencialGCP(BaseModel):
    service_account_json: str

class CredencialAzure(BaseModel):
    connection_string: str

# ── Funcoes de autenticacao ─────────────────────────────────
def verificar_senha(senha_plana, senha_hash):
    return pwd_context.verify(senha_plana, senha_hash)

def gerar_hash_senha(senha_plana: str) -> str:
    return pwd_context.hash(senha_plana)

def criar_token(dados: dict):
    copia = dados.copy()
    expira = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRA_EM)
    copia.update({"exp": expira})
    return jwt.encode(copia, SECRET_KEY, algorithm=ALGORITHM)

def chave_rate_limit_login(request: Request, email: str) -> str:
    ip = request.client.host if request.client else "desconhecido"
    return f"{ip}:{email.lower()}"

def verificar_rate_limit_login(chave: str):
    agora = monotonic()
    tentativas = _tentativas_login[chave]
    while tentativas and agora - tentativas[0] > LOGIN_JANELA_SEGUNDOS:
        tentativas.popleft()
    if len(tentativas) >= LOGIN_MAX_TENTATIVAS:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas de login. Aguarde alguns minutos e tente novamente.",
        )

def registrar_falha_login(chave: str):
    _tentativas_login[chave].append(monotonic())

def limpar_falhas_login(chave: str):
    _tentativas_login.pop(chave, None)

def usuario_atual(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("uid")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    usuario = buscar_usuario_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido")
    return usuario

# ── Rotas de autenticacao e cadastro ──────────────────────────
@app.post("/cadastro", response_model=Token)
def cadastro(dados: CadastroRequest):
    if dados.plano not in PLANOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Plano invalido")
    if len(dados.senha) < 8:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 8 caracteres")
    if buscar_usuario_por_email(dados.email):
        raise HTTPException(status_code=409, detail="Ja existe uma conta com esse e-mail")

    senha_hash = gerar_hash_senha(dados.senha)
    novo = criar_usuario(dados.email, senha_hash, dados.plano)
    token = criar_token({"sub": novo["email"], "uid": novo["id"]})
    registrar_acesso(novo["email"], "CADASTRO", "-", "-", f"plano {novo['plano']}")
    return {"access_token": token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    chave_login = chave_rate_limit_login(request, form.username)
    verificar_rate_limit_login(chave_login)

    usuario = buscar_usuario_por_email(form.username)
    if not usuario:
        registrar_falha_login(chave_login)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    if not verificar_senha(form.password, usuario["senha_hash"]):
        registrar_falha_login(chave_login)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    limpar_falhas_login(chave_login)
    token = criar_token({"sub": usuario["email"], "uid": usuario["id"]})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me")
def meus_dados(usuario=Depends(usuario_atual)):
    providers = listar_providers_configurados(usuario["id"])
    return {
        "email": usuario["email"],
        "plano": usuario["plano"],
        "is_admin": usuario["is_admin"],
        "providers_configurados": providers,
    }

@app.patch("/me/plano")
def atualizar_meu_plano(dados: PlanoRequest, usuario=Depends(usuario_atual)):
    if dados.plano not in PLANOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Plano invalido")
    atualizado = atualizar_plano_usuario(usuario["id"], dados.plano)
    registrar_acesso(usuario["email"], "PLANO", "-", "-", f"plano {dados.plano}")
    return {
        "email": atualizado["email"],
        "plano": atualizado["plano"],
        "is_admin": atualizado["is_admin"],
    }

# ── Rotas de gerenciamento de credenciais de nuvem ────────────
@app.post("/credenciais/aws")
def cadastrar_credencial_aws(dados: CredencialAWS, usuario=Depends(usuario_atual)):
    salvar_credencial(usuario["id"], "aws", dados.dict())
    registrar_acesso(usuario["email"], "CREDENCIAL", "aws", "-", "credencial cadastrada")
    return {"status": "ok", "provider": "aws"}

@app.post("/credenciais/gcp")
def cadastrar_credencial_gcp(dados: CredencialGCP, usuario=Depends(usuario_atual)):
    salvar_credencial(usuario["id"], "gcp", dados.dict())
    registrar_acesso(usuario["email"], "CREDENCIAL", "gcp", "-", "credencial cadastrada")
    return {"status": "ok", "provider": "gcp"}

@app.post("/credenciais/azure")
def cadastrar_credencial_azure(dados: CredencialAzure, usuario=Depends(usuario_atual)):
    salvar_credencial(usuario["id"], "azure", dados.dict())
    registrar_acesso(usuario["email"], "CREDENCIAL", "azure", "-", "credencial cadastrada")
    return {"status": "ok", "provider": "azure"}

# ── Providers: autenticacao por usuario, com fallback para o admin ───
def obter_provider_autenticado(provider: str, usuario: dict):
    """
    Retorna uma instancia autenticada do provider solicitado, usando as
    credenciais PROPRIAS do usuario logado. Excecao: a conta admin, se nao
    tiver credenciais cadastradas, usa as credenciais do sistema (IAM Role
    da task para AWS; connection string do sistema para Azure) como fallback.
    """
    credencial = buscar_credencial(usuario["id"], provider)

    if provider == "gcp":
        p = GCSReader()
        if credencial:
            ok = p.authenticate(credencial)
        elif usuario["is_admin"]:
            ok = p.authenticate({})
        else:
            raise ValueError("Nenhuma credencial GCP cadastrada para este usuario")
        if not ok:
            raise ValueError("Falha ao autenticar no GCP com as credenciais fornecidas")
        return p

    if provider == "azure":
        p = BlobReader()
        if credencial:
            ok = p.authenticate(credencial)
        elif usuario["is_admin"]:
            # Fallback: conta admin sem credenciais proprias usa a connection
            # string do sistema (variavel de ambiente AZURE_STORAGE_CONNECTION_STRING)
            ok = p.authenticate({})
        else:
            raise ValueError("Nenhuma credencial Azure cadastrada para este usuario")
        if not ok:
            raise ValueError("Falha ao autenticar no Azure com as credenciais fornecidas")
        return p

    if provider == "aws":
        p = S3Reader()
        if credencial:
            p.authenticate(credencial)
        elif usuario["is_admin"]:
            p.authenticate({'mode': 'env'})
        else:
            raise ValueError("Nenhuma credencial AWS cadastrada para este usuario")
        return p

    raise ValueError("Provider não encontrado")

def responder_erro_operacional(erro: Exception):
    if isinstance(erro, ValueError):
        raise HTTPException(status_code=400, detail=str(erro))
    if isinstance(erro, (ClientError, AzureError, GoogleAPIError)):
        raise HTTPException(status_code=502, detail="Falha ao consultar o provider de nuvem")
    raise HTTPException(status_code=500, detail="Erro interno ao processar a solicitacao")

@app.get("/list/{provider}")
def list_resources(provider: str, usuario=Depends(usuario_atual)):
    if provider not in PROVIDERS_VALIDOS:
        raise HTTPException(status_code=404, detail="Provider não encontrado")
    try:
        p = obter_provider_autenticado(provider, usuario)
        resources = list(p.list_resources())
        registrar_acesso(usuario["email"], "LIST", provider, "-", f"{len(resources)} recursos")
        return {"provider": provider, "resources": resources}
    except Exception as e:
        responder_erro_operacional(e)

@app.get("/read/{provider}/{bucket}")
def read_resource(provider: str, bucket: str, usuario=Depends(usuario_atual)):
    if provider not in PROVIDERS_VALIDOS:
        raise HTTPException(status_code=404, detail="Provider não encontrado")
    try:
        p = obter_provider_autenticado(provider, usuario)

        prefix = f"gs://{bucket}/dados/" if provider == "gcp" else \
                 f"azure://{bucket}/dados/" if provider == "azure" else \
                 f"s3://{bucket}/"

        records = list(p.read(prefix))
        registrar_acesso(usuario["email"], "READ", provider, bucket, f"{len(records)} registros")
        return {"provider": provider, "bucket": bucket, "records": records}
    except Exception as e:
        responder_erro_operacional(e)

@app.get("/audit")
def ver_logs(usuario=Depends(usuario_atual)):
    try:
        logs = buscar_logs_auditoria(limite=50)
        return {"logs": logs}
    except Exception as e:
        responder_erro_operacional(e)

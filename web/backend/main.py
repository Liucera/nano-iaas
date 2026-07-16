import sys
import os
import json
import hmac
import ipaddress
import math
import threading
from hashlib import sha256
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
from pydantic import BaseModel, EmailStr, field_validator
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
PLANOS_VALORES = {"gratuito": 0, "popular": 100, "premium": 1000}
PROVIDERS_VALIDOS = ("gcp", "azure", "aws")
def _env_int(nome: str, padrao: int) -> int:
    try:
        valor = int(os.environ.get(nome, str(padrao)))
    except ValueError as exc:
        raise RuntimeError(f"{nome} deve ser um numero inteiro") from exc
    if valor < 1:
        raise RuntimeError(f"{nome} deve ser maior que zero")
    return valor

def _env_bool(nome: str, padrao: bool = False) -> bool:
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    normalizado = valor.strip().casefold()
    if normalizado in {"1", "true", "yes", "on"}:
        return True
    if normalizado in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{nome} deve ser true ou false")

LOGIN_RATE_LIMIT_ACCOUNT_MAX_ATTEMPTS = _env_int("LOGIN_RATE_LIMIT_ACCOUNT_MAX_ATTEMPTS", 10)
LOGIN_RATE_LIMIT_ACCOUNT_IP_MAX_ATTEMPTS = _env_int("LOGIN_RATE_LIMIT_ACCOUNT_IP_MAX_ATTEMPTS", 5)
LOGIN_RATE_LIMIT_WINDOW_SECONDS = _env_int("LOGIN_RATE_LIMIT_WINDOW_SECONDS", 300)
LOGIN_RATE_LIMIT_BLOCK_SECONDS = _env_int("LOGIN_RATE_LIMIT_BLOCK_SECONDS", 900)
LOGIN_RATE_LIMIT_RETENTION_SECONDS = _env_int("LOGIN_RATE_LIMIT_RETENTION_SECONDS", 86400)
LOGIN_TRUST_PROXY_HEADERS = _env_bool("LOGIN_TRUST_PROXY_HEADERS", False)
VERSAO_TERMOS_ATUAL = "2026-07-15"
VERSAO_PRIVACIDADE_ATUAL = "2026-07-15"
HASH_SENHA_FICTICIA = "$2b$12$eDn400ftB4k.B.6YDEPycu3a4hKrjVCY8mQE39S2LL7XWEID36Rt2"
_chave_rate_limit = None
_ultima_limpeza_rate_limit = 0.0
_lock_limpeza_rate_limit = threading.Lock()

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
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS aceite_termos BOOLEAN NOT NULL DEFAULT false;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS versao_termos TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS data_aceite_termos TIMESTAMPTZ;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_version TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_version TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMPTZ;")
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pix_payment_requests (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    email TEXT NOT NULL,
                    plano TEXT NOT NULL,
                    valor_centavos INTEGER NOT NULL,
                    comprovante TEXT,
                    status TEXT NOT NULL DEFAULT 'pendente',
                    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
                    aprovado_em TIMESTAMPTZ
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    attempt_key VARCHAR(64) PRIMARY KEY,
                    scope VARCHAR(20) NOT NULL CHECK (scope IN ('account', 'account_ip')),
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    window_started_at TIMESTAMPTZ NOT NULL,
                    blocked_until TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_login_attempts_updated_at
                ON login_attempts (updated_at);
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
                "SELECT id, email, senha_hash, plano, is_admin FROM users WHERE lower(email) = lower(%s)",
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
                "SELECT id, full_name, email, plano, is_admin FROM users WHERE id = %s",
                (user_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()

def criar_usuario(
    full_name: str,
    email: str,
    senha_hash: str,
    aceite_termos: bool,
    aceite_privacidade: bool,
    terms_version: str,
    privacy_version: str,
):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO users (
                    full_name, email, senha_hash, plano, is_admin,
                    aceite_termos, versao_termos, data_aceite_termos,
                    terms_version, terms_accepted_at,
                    privacy_version, privacy_accepted_at
                )
                VALUES (
                    %s, %s, %s, 'gratuito', false,
                    %s, %s, CASE WHEN %s THEN now() ELSE NULL END,
                    %s, CASE WHEN %s THEN now() ELSE NULL END,
                    %s, CASE WHEN %s THEN now() ELSE NULL END
                )
                RETURNING id, full_name, email, plano, is_admin
                """,
                (
                    full_name, email, senha_hash,
                    aceite_termos, terms_version, aceite_termos,
                    terms_version, aceite_termos,
                    privacy_version, aceite_privacidade,
                ),
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

def criar_solicitacao_pix(usuario: dict, plano: str, comprovante: str = ""):
    valor_centavos = PLANOS_VALORES[plano] * 100
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO pix_payment_requests (user_id, email, plano, valor_centavos, comprovante)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, email, plano, valor_centavos, comprovante, status, criado_em
                """,
                (usuario["id"], usuario["email"], plano, valor_centavos, comprovante),
            )
            solicitacao = cur.fetchone()
        conn.commit()
        return solicitacao
    finally:
        conn.close()

def listar_solicitacoes_pix(status: str = "pendente", limite: int = 50):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id, email, plano, valor_centavos, comprovante, status, criado_em, aprovado_em
                FROM pix_payment_requests
                WHERE status = %s
                ORDER BY criado_em DESC
                LIMIT %s
                """,
                (status, limite),
            )
            return cur.fetchall()
    finally:
        conn.close()

def aprovar_solicitacao_pix(solicitacao_id: int):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE pix_payment_requests
                SET status = 'aprovado', aprovado_em = now()
                WHERE id = %s AND status = 'pendente'
                RETURNING id, user_id, email, plano, valor_centavos, status, aprovado_em
                """,
                (solicitacao_id,),
            )
            solicitacao = cur.fetchone()
            if not solicitacao:
                conn.rollback()
                return None
            cur.execute(
                """
                UPDATE users
                SET plano = %s
                WHERE id = %s
                RETURNING id, email, plano, is_admin
                """,
                (solicitacao["plano"], solicitacao["user_id"]),
            )
            usuario = cur.fetchone()
        conn.commit()
        return {"solicitacao": solicitacao, "usuario": usuario}
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
    allow_origins=[
        "https://liucera.github.io",
        "https://app.nano-iaas.com.br",
        "https://nano-iaas.com.br",
        "http://localhost:3000",
    ],
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
    full_name: str
    email: EmailStr
    senha: str
    plano: str = "gratuito"
    aceite_termos: bool
    aceite_privacidade: bool
    terms_version: str
    privacy_version: str

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

class MeResponse(BaseModel):
    full_name: str | None
    email: EmailStr
    plano: str
    is_admin: bool
    providers_configurados: list[str]

class PlanoRequest(BaseModel):
    plano: str

class PixRequest(BaseModel):
    plano: str
    comprovante: str = ""

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

def resolver_ip_cliente(request: Request, confiar_proxy: bool | None = None) -> str:
    confiar = LOGIN_TRUST_PROXY_HEADERS if confiar_proxy is None else confiar_proxy
    fallback = request.client.host if request.client else "desconhecido"
    if not confiar:
        return fallback

    encaminhados = request.headers.get("x-forwarded-for", "")
    for candidato in encaminhados.split(","):
        candidato = candidato.strip()
        if not candidato:
            continue
        try:
            return str(ipaddress.ip_address(candidato))
        except ValueError:
            continue
    return fallback

def obter_chave_rate_limit() -> bytes:
    global _chave_rate_limit
    if _chave_rate_limit is None:
        chave_mestra = obter_chave_criptografia()
        _chave_rate_limit = hmac.new(
            chave_mestra,
            b"nano-iaas:login-rate-limit:key",
            sha256,
        ).digest()
    return _chave_rate_limit

def gerar_chaves_rate_limit(username: str, client_ip: str) -> dict[str, str]:
    normalizado = username.strip().casefold()
    chave = obter_chave_rate_limit()

    def assinar(conteudo: str) -> str:
        return hmac.new(chave, conteudo.encode(), sha256).hexdigest()

    return {
        "account": assinar(f"login-account:{normalizado}"),
        "account_ip": assinar(f"login-account-ip:{normalizado}:{client_ip}"),
    }

def _retry_after(blocked_until, agora) -> int:
    return max(1, math.ceil((blocked_until - agora).total_seconds()))

def _limite_por_escopo(scope: str) -> int:
    if scope == "account":
        return LOGIN_RATE_LIMIT_ACCOUNT_MAX_ATTEMPTS
    if scope == "account_ip":
        return LOGIN_RATE_LIMIT_ACCOUNT_IP_MAX_ATTEMPTS
    raise ValueError("Escopo de rate limit invalido")

def verificar_bloqueios_login(chaves: dict[str, str]) -> int | None:
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT NOW();")
            agora = cur.fetchone()[0]
            maior_retry_after = 0

            for scope, attempt_key in sorted(chaves.items(), key=lambda item: item[1]):
                cur.execute(
                    """
                    SELECT failure_count, window_started_at, blocked_until
                    FROM login_attempts
                    WHERE attempt_key = %s
                    FOR UPDATE
                    """,
                    (attempt_key,),
                )
                registro = cur.fetchone()
                if not registro:
                    continue

                _, window_started_at, blocked_until = registro
                if blocked_until and blocked_until > agora:
                    maior_retry_after = max(
                        maior_retry_after,
                        _retry_after(blocked_until, agora),
                    )
                    continue

                janela_expirada = (
                    agora >= window_started_at + timedelta(seconds=LOGIN_RATE_LIMIT_WINDOW_SECONDS)
                )
                if blocked_until is not None or janela_expirada:
                    cur.execute(
                        """
                        UPDATE login_attempts
                        SET failure_count = 0,
                            window_started_at = %s,
                            blocked_until = NULL,
                            updated_at = %s
                        WHERE attempt_key = %s
                        """,
                        (agora, agora, attempt_key),
                    )

        conn.commit()
        return maior_retry_after or None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def registrar_falhas_login(chaves: dict[str, str]) -> int | None:
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT NOW();")
            agora = cur.fetchone()[0]
            maior_retry_after = 0

            for scope, attempt_key in sorted(chaves.items(), key=lambda item: item[1]):
                cur.execute(
                    """
                    INSERT INTO login_attempts (
                        attempt_key, scope, failure_count, window_started_at, updated_at
                    )
                    VALUES (%s, %s, 0, %s, %s)
                    ON CONFLICT (attempt_key) DO NOTHING
                    """,
                    (attempt_key, scope, agora, agora),
                )
                cur.execute(
                    """
                    SELECT failure_count, window_started_at, blocked_until
                    FROM login_attempts
                    WHERE attempt_key = %s
                    FOR UPDATE
                    """,
                    (attempt_key,),
                )
                failure_count, window_started_at, blocked_until = cur.fetchone()

                if blocked_until and blocked_until > agora:
                    maior_retry_after = max(
                        maior_retry_after,
                        _retry_after(blocked_until, agora),
                    )
                    continue

                janela_expirada = (
                    agora >= window_started_at + timedelta(seconds=LOGIN_RATE_LIMIT_WINDOW_SECONDS)
                )
                if blocked_until is not None or janela_expirada:
                    failure_count = 0
                    window_started_at = agora

                failure_count += 1
                novo_bloqueio = None
                if failure_count >= _limite_por_escopo(scope):
                    novo_bloqueio = agora + timedelta(seconds=LOGIN_RATE_LIMIT_BLOCK_SECONDS)
                    maior_retry_after = max(
                        maior_retry_after,
                        _retry_after(novo_bloqueio, agora),
                    )

                cur.execute(
                    """
                    UPDATE login_attempts
                    SET failure_count = %s,
                        window_started_at = %s,
                        blocked_until = %s,
                        updated_at = %s
                    WHERE attempt_key = %s
                    """,
                    (
                        failure_count,
                        window_started_at,
                        novo_bloqueio,
                        agora,
                        attempt_key,
                    ),
                )

        conn.commit()
        return maior_retry_after or None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def limpar_falhas_login(chaves: dict[str, str]):
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM login_attempts WHERE attempt_key = ANY(%s);",
                (list(chaves.values()),),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def limpar_tentativas_login_expiradas():
    global _ultima_limpeza_rate_limit
    agora_monotonic = monotonic()
    if agora_monotonic - _ultima_limpeza_rate_limit < 60:
        return
    if not _lock_limpeza_rate_limit.acquire(blocking=False):
        return

    conn = None
    try:
        if monotonic() - _ultima_limpeza_rate_limit < 60:
            return
        _ultima_limpeza_rate_limit = monotonic()
        conn = conectar_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH expirados AS (
                    SELECT attempt_key
                    FROM login_attempts
                    WHERE updated_at < NOW() - (%s * INTERVAL '1 second')
                    ORDER BY updated_at
                    LIMIT 100
                )
                DELETE FROM login_attempts
                WHERE attempt_key IN (SELECT attempt_key FROM expirados)
                """,
                (LOGIN_RATE_LIMIT_RETENTION_SECONDS,),
            )
        conn.commit()
    except Exception:
        if conn is not None:
            conn.rollback()
    finally:
        if conn is not None:
            conn.close()
        _lock_limpeza_rate_limit.release()

def executar_protecao_login(operacao, *args):
    try:
        return operacao(*args)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Servico de autenticacao temporariamente indisponivel",
        ) from None

def erro_muitas_tentativas(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="Muitas tentativas de login. Tente novamente mais tarde.",
        headers={"Retry-After": str(max(1, retry_after))},
    )

def obter_config_pix():
    return {
        "chave": os.environ.get("NANO_IAAS_PIX_KEY", "arlindo.barroso100@yahoo.com"),
        "recebedor": os.environ.get("NANO_IAAS_PIX_RECEIVER", "Arlindo da Silva Barroso"),
        "cidade": os.environ.get("NANO_IAAS_PIX_CITY", "Pacatuba, Ceara"),
        "instrucao": "Envie o Pix e informe o identificador/comprovante para aprovacao manual.",
        "planos": {
            "popular": {"valor": PLANOS_VALORES["popular"], "descricao": "Plano Popular"},
            "premium": {"valor": PLANOS_VALORES["premium"], "descricao": "Plano Premium"},
        },
    }

def exigir_admin(usuario: dict):
    if not usuario.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")

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
    full_name = dados.full_name.strip()
    email = str(dados.email).strip().lower()
    if len(full_name) < 3:
        raise HTTPException(status_code=400, detail="O nome completo deve ter pelo menos 3 caracteres")
    if len(full_name) > 150:
        raise HTTPException(status_code=400, detail="O nome completo deve ter no maximo 150 caracteres")
    if dados.plano not in PLANOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Plano invalido")
    if len(dados.senha) < 8:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 8 caracteres")
    if not dados.aceite_termos:
        raise HTTPException(status_code=400, detail="Aceite os Termos de Uso para criar a conta")
    if not dados.aceite_privacidade:
        raise HTTPException(status_code=400, detail="Aceite a Política de Privacidade para criar a conta")
    if dados.terms_version != VERSAO_TERMOS_ATUAL:
        raise HTTPException(status_code=400, detail="Versao dos Termos de Uso invalida")
    if dados.privacy_version != VERSAO_PRIVACIDADE_ATUAL:
        raise HTTPException(status_code=400, detail="Versao da Política de Privacidade invalida")
    if buscar_usuario_por_email(email):
        raise HTTPException(status_code=409, detail="Ja existe uma conta com esse e-mail")

    senha_hash = gerar_hash_senha(dados.senha)
    novo = criar_usuario(
        full_name,
        email,
        senha_hash,
        dados.aceite_termos,
        dados.aceite_privacidade,
        dados.terms_version,
        dados.privacy_version,
    )
    token = criar_token({"sub": novo["email"], "uid": novo["id"]})
    registrar_acesso(novo["email"], "CADASTRO", "-", "-", "plano inicial gratuito")
    return {"access_token": token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    client_ip = resolver_ip_cliente(request)
    chaves_login = gerar_chaves_rate_limit(form.username, client_ip)
    limpar_tentativas_login_expiradas()

    retry_after = executar_protecao_login(verificar_bloqueios_login, chaves_login)
    if retry_after:
        raise erro_muitas_tentativas(retry_after)

    usuario = buscar_usuario_por_email(form.username)
    if usuario:
        credenciais_validas = verificar_senha(form.password, usuario["senha_hash"])
    else:
        verificar_senha(form.password, HASH_SENHA_FICTICIA)
        credenciais_validas = False

    if not credenciais_validas:
        retry_after = executar_protecao_login(registrar_falhas_login, chaves_login)
        if retry_after:
            raise erro_muitas_tentativas(retry_after)
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    executar_protecao_login(limpar_falhas_login, chaves_login)
    token = criar_token({"sub": usuario["email"], "uid": usuario["id"]})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me", response_model=MeResponse)
def meus_dados(usuario=Depends(usuario_atual)):
    providers = listar_providers_configurados(usuario["id"])
    return {
        "full_name": usuario.get("full_name"),
        "email": usuario["email"],
        "plano": usuario["plano"],
        "is_admin": usuario["is_admin"],
        "providers_configurados": providers,
    }

@app.get("/pix")
def dados_pix(usuario=Depends(usuario_atual)):
    return obter_config_pix()

@app.post("/pix/solicitacao")
def solicitar_ativacao_pix(dados: PixRequest, usuario=Depends(usuario_atual)):
    if dados.plano not in ("popular", "premium"):
        raise HTTPException(status_code=400, detail="Plano Pix invalido")
    solicitacao = criar_solicitacao_pix(usuario, dados.plano, dados.comprovante)
    registrar_acesso(usuario["email"], "PIX_SOLICITADO", "-", "-", f"plano {dados.plano}")
    return {
        "id": solicitacao["id"],
        "status": solicitacao["status"],
        "plano": solicitacao["plano"],
        "valor": solicitacao["valor_centavos"] / 100,
        "pix": obter_config_pix(),
    }

@app.get("/admin/pix/solicitacoes")
def admin_listar_pix(status: str = "pendente", usuario=Depends(usuario_atual)):
    exigir_admin(usuario)
    solicitacoes = listar_solicitacoes_pix(status=status)
    return {"solicitacoes": [dict(s) for s in solicitacoes]}

@app.post("/admin/pix/solicitacoes/{solicitacao_id}/aprovar")
def admin_aprovar_pix(solicitacao_id: int, usuario=Depends(usuario_atual)):
    exigir_admin(usuario)
    resultado = aprovar_solicitacao_pix(solicitacao_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Solicitacao Pix pendente nao encontrada")
    registrar_acesso(usuario["email"], "PIX_APROVADO", "-", str(solicitacao_id), resultado["usuario"]["email"])
    return resultado

@app.patch("/me/plano")
def atualizar_meu_plano(dados: PlanoRequest, usuario=Depends(usuario_atual)):
    if dados.plano not in PLANOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Plano invalido")
    if dados.plano != "gratuito":
        raise HTTPException(status_code=402, detail="Planos pagos exigem solicitacao Pix em /pix/solicitacao")
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

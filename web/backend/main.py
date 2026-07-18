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
from uuid import UUID

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import boto3
import psycopg2
import psycopg2.extras
from botocore.exceptions import ClientError
from azure.core.exceptions import AzureError

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
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
VERSAO_LEGADA_CADASTRO = "beta-2026-07"
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

def buscar_senha_hash_usuario(user_id: int):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, senha_hash FROM users WHERE id = %s",
                (user_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()

def atualizar_senha_usuario(user_id: int, novo_hash: str, usuario_email: str) -> bool:
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET senha_hash = %s
                WHERE id = %s
                RETURNING id
                """,
                (novo_hash, user_id),
            )
            atualizado = cur.fetchone()
        if not atualizado:
            conn.rollback()
            return False
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider, recurso, detalhes)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (usuario_email, "SENHA", "-", "-", "senha alterada"),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
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

def atualizar_plano_proprio(user_id: int, plano: str):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, email, plano, is_admin
                FROM users
                WHERE id = %s
                FOR UPDATE
                """,
                (user_id,),
            )
            usuario = cur.fetchone()
            if not usuario:
                conn.rollback()
                return None

            plano_anterior = usuario["plano"]
            if plano != "gratuito" and plano_anterior != plano:
                conn.rollback()
                return {
                    "plano_anterior": plano_anterior,
                    "plano": plano_anterior,
                    "alterado": False,
                    "bloqueado": True,
                }
            alterado = plano_anterior != plano
            if alterado:
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

            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider, recurso, detalhes)
                VALUES (%s, %s, '-', 'plano', %s)
                """,
                (
                    usuario["email"],
                    "PLANO_ATUALIZADO" if alterado else "PLANO_MANTIDO",
                    f"plano_anterior={plano_anterior};plano_novo={plano}",
                ),
            )
        conn.commit()
        return {
            "plano_anterior": plano_anterior,
            "plano": usuario["plano"],
            "alterado": alterado,
            "bloqueado": False,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def criar_solicitacao_pix(user_id: int, plano: str, comprovante: str = ""):
    valor_centavos = PLANOS_VALORES[plano] * 100
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, email, plano
                FROM users
                WHERE id = %s
                FOR UPDATE
                """,
                (user_id,),
            )
            usuario = cur.fetchone()
            if not usuario:
                conn.rollback()
                return "missing_user", None
            if usuario["plano"] == plano:
                conn.rollback()
                return "already_active", None

            cur.execute(
                """
                SELECT id, plano
                FROM pix_payment_requests
                WHERE user_id = %s AND status = 'pendente'
                ORDER BY id
                LIMIT 1
                FOR UPDATE
                """,
                (user_id,),
            )
            if cur.fetchone():
                conn.rollback()
                return "pending", None

            cur.execute(
                """
                INSERT INTO pix_payment_requests (user_id, email, plano, valor_centavos, comprovante)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, email, plano, valor_centavos, comprovante, status, criado_em
                """,
                (user_id, usuario["email"], plano, valor_centavos, comprovante),
            )
            solicitacao = cur.fetchone()
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider, recurso, detalhes)
                VALUES (%s, 'PIX_SOLICITADO', '-', 'plano', %s)
                """,
                (usuario["email"], f"plano_solicitado={plano}"),
            )
        conn.commit()
        return "ok", solicitacao
    except Exception:
        conn.rollback()
        raise
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

def aprovar_solicitacao_pix(solicitacao_id: int, admin_email: str):
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT user_id
                FROM pix_payment_requests
                WHERE id = %s AND status = 'pendente'
                """,
                (solicitacao_id,),
            )
            candidato = cur.fetchone()
            if not candidato:
                conn.rollback()
                return None

            cur.execute(
                """
                SELECT id, email, plano, is_admin
                FROM users
                WHERE id = %s
                FOR UPDATE
                """,
                (candidato["user_id"],),
            )
            usuario = cur.fetchone()
            if not usuario:
                conn.rollback()
                return "invalid"
            plano_anterior = usuario["plano"]

            cur.execute(
                """
                SELECT id, user_id, email, plano, valor_centavos, status
                FROM pix_payment_requests
                WHERE id = %s AND status = 'pendente'
                FOR UPDATE
                """,
                (solicitacao_id,),
            )
            solicitacao = cur.fetchone()
            if not solicitacao:
                conn.rollback()
                return None
            if (
                solicitacao["user_id"] != usuario["id"]
                or solicitacao["plano"] not in ("popular", "premium")
                or solicitacao["valor_centavos"] != PLANOS_VALORES[solicitacao["plano"]] * 100
            ):
                conn.rollback()
                return "invalid"

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
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider, recurso, detalhes)
                VALUES (%s, 'PIX_APROVADO', '-', %s, %s)
                """,
                (
                    admin_email,
                    str(solicitacao_id),
                    f"plano_anterior={plano_anterior};plano_novo={solicitacao['plano']}",
                ),
            )
        conn.commit()
        return {"solicitacao": solicitacao, "usuario": usuario}
    except Exception:
        conn.rollback()
        raise
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


def mascarar_access_key_id(valor: str) -> str:
    valor = valor.strip()
    if len(valor) <= 8:
        return "*" * max(4, len(valor))
    return f"{valor[:4]}{'*' * (len(valor) - 8)}{valor[-4:]}"

def mascarar_secret_access_key(valor: str) -> str:
    valor = valor.strip()
    if len(valor) <= 4:
        return "*" * max(4, len(valor))
    return f"{'*' * 8}{valor[-4:]}"

def _metadata_credencial_aws(linha: dict) -> dict:
    credencial = json.loads(descriptografar(linha["credencial_cifrada"]))
    return {
        "id": linha["id"],
        "provider": "aws",
        "access_key_id_masked": mascarar_access_key_id(credencial["access_key_id"]),
        "secret_access_key_masked": mascarar_secret_access_key(credencial["secret_access_key"]),
        "criado_em": linha["criado_em"],
    }

def listar_credenciais_aws_usuario(user_id: int) -> list[dict]:
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, credencial_cifrada, criado_em
                FROM cloud_credentials
                WHERE user_id = %s AND provider = 'aws'
                ORDER BY id
                """,
                (user_id,),
            )
            linhas = cur.fetchall()
        return [_metadata_credencial_aws(linha) for linha in linhas]
    finally:
        conn.close()

def salvar_credencial_aws_usuario(
    user_id: int,
    usuario_email: str,
    credencial_json: dict,
    substituir: bool,
) -> tuple[str, dict | None]:
    cifrado = criptografar(json.dumps(credencial_json))
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id
                FROM cloud_credentials
                WHERE user_id = %s AND provider = 'aws'
                FOR UPDATE
                """,
                (user_id,),
            )
            existente = cur.fetchone()
            if existente and not substituir:
                conn.rollback()
                return "exists", None
            if not existente and substituir:
                conn.rollback()
                return "missing", None

            if substituir:
                cur.execute(
                    """
                    UPDATE cloud_credentials
                    SET credencial_cifrada = %s, criado_em = now()
                    WHERE user_id = %s AND provider = 'aws'
                    RETURNING id, credencial_cifrada, criado_em
                    """,
                    (cifrado, user_id),
                )
                acao = "CREDENCIAL_SUBSTITUIDA"
            else:
                cur.execute(
                    """
                    INSERT INTO cloud_credentials (user_id, provider, credencial_cifrada)
                    VALUES (%s, 'aws', %s)
                    RETURNING id, credencial_cifrada, criado_em
                    """,
                    (user_id, cifrado),
                )
                acao = "CREDENCIAL_CADASTRADA"

            linha = cur.fetchone()
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider)
                VALUES (%s, %s, 'aws')
                """,
                (usuario_email, acao),
            )
        conn.commit()
        return "ok", _metadata_credencial_aws(linha)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def excluir_credencial_aws_usuario(user_id: int, usuario_email: str) -> bool:
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM cloud_credentials
                WHERE user_id = %s AND provider = 'aws'
                FOR UPDATE
                """,
                (user_id,),
            )
            if not cur.fetchone():
                conn.rollback()
                return False
            cur.execute(
                """
                DELETE FROM cloud_credentials
                WHERE user_id = %s AND provider = 'aws'
                """,
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider)
                VALUES (%s, 'CREDENCIAL_EXCLUIDA', 'aws')
                """,
                (usuario_email,),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mascarar_client_email_gcp(valor: str) -> str:
    local, separador, dominio = valor.strip().partition("@")
    if not separador or not local or not dominio:
        return "***"
    partes_dominio = dominio.split(".")
    primeiro_rotulo = partes_dominio[0]
    local_mascarado = f"{local[:2]}***" if len(local) > 1 else f"{local[:1]}***"
    dominio_mascarado = (
        f"{primeiro_rotulo[:2]}***" if len(primeiro_rotulo) > 1 else f"{primeiro_rotulo[:1]}***"
    )
    if len(partes_dominio) > 1:
        dominio_mascarado += "." + ".".join(partes_dominio[1:])
    return f"{local_mascarado}@{dominio_mascarado}"


def _info_service_account_gcp(credencial: dict) -> dict:
    service_account_json = credencial.get("service_account_json")
    if not isinstance(service_account_json, str):
        raise ValueError("Credencial GCP armazenada em formato inválido")
    info = json.loads(service_account_json)
    if not isinstance(info, dict):
        raise ValueError("Credencial GCP armazenada em formato inválido")
    return info


def _metadata_credencial_gcp(linha: dict) -> dict:
    credencial = json.loads(descriptografar(linha["credencial_cifrada"]))
    info = _info_service_account_gcp(credencial)
    return {
        "id": linha["id"],
        "provider": "gcp",
        "project_id": info["project_id"],
        "client_email_masked": mascarar_client_email_gcp(info["client_email"]),
        "criado_em": linha["criado_em"],
    }


def listar_credenciais_gcp_usuario(user_id: int) -> list[dict]:
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, credencial_cifrada, criado_em
                FROM cloud_credentials
                WHERE user_id = %s AND provider = 'gcp'
                ORDER BY id
                """,
                (user_id,),
            )
            linhas = cur.fetchall()
        return [_metadata_credencial_gcp(linha) for linha in linhas]
    finally:
        conn.close()


def salvar_credencial_gcp_usuario(
    user_id: int,
    usuario_email: str,
    credencial_json: dict,
    substituir: bool,
) -> tuple[str, dict | None]:
    cifrado = criptografar(json.dumps(credencial_json, ensure_ascii=False))
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id
                FROM cloud_credentials
                WHERE user_id = %s AND provider = 'gcp'
                FOR UPDATE
                """,
                (user_id,),
            )
            existente = cur.fetchone()
            if existente and not substituir:
                conn.rollback()
                return "exists", None
            if not existente and substituir:
                conn.rollback()
                return "missing", None

            if substituir:
                cur.execute(
                    """
                    UPDATE cloud_credentials
                    SET credencial_cifrada = %s, criado_em = now()
                    WHERE user_id = %s AND provider = 'gcp'
                    RETURNING id, credencial_cifrada, criado_em
                    """,
                    (cifrado, user_id),
                )
                acao = "CREDENCIAL_SUBSTITUIDA"
            else:
                cur.execute(
                    """
                    INSERT INTO cloud_credentials (user_id, provider, credencial_cifrada)
                    VALUES (%s, 'gcp', %s)
                    RETURNING id, credencial_cifrada, criado_em
                    """,
                    (user_id, cifrado),
                )
                acao = "CREDENCIAL_CADASTRADA"

            linha = cur.fetchone()
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider)
                VALUES (%s, %s, 'gcp')
                """,
                (usuario_email, acao),
            )
        conn.commit()
        return "ok", _metadata_credencial_gcp(linha)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def excluir_credencial_gcp_usuario(user_id: int, usuario_email: str) -> bool:
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM cloud_credentials
                WHERE user_id = %s AND provider = 'gcp'
                FOR UPDATE
                """,
                (user_id,),
            )
            if not cur.fetchone():
                conn.rollback()
                return False
            cur.execute(
                """
                DELETE FROM cloud_credentials
                WHERE user_id = %s AND provider = 'gcp'
                """,
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider)
                VALUES (%s, 'CREDENCIAL_EXCLUIDA', 'gcp')
                """,
                (usuario_email,),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mascarar_identificador_azure(valor: str) -> str:
    valor = valor.strip()
    if len(valor) <= 8:
        return "*" * max(4, len(valor))
    return f"{valor[:4]}{'*' * (len(valor) - 8)}{valor[-4:]}"


def _metadata_credencial_azure(linha: dict) -> dict:
    credencial = json.loads(descriptografar(linha["credencial_cifrada"]))
    return {
        "id": linha["id"],
        "provider": "azure",
        "tenant_id_masked": mascarar_identificador_azure(credencial["tenant_id"]),
        "client_id_masked": mascarar_identificador_azure(credencial["client_id"]),
        "subscription_id_masked": mascarar_identificador_azure(credencial["subscription_id"]),
        "criado_em": linha["criado_em"],
    }


def listar_credenciais_azure_usuario(user_id: int) -> list[dict]:
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, credencial_cifrada, criado_em
                FROM cloud_credentials
                WHERE user_id = %s AND provider = 'azure'
                ORDER BY id
                """,
                (user_id,),
            )
            linhas = cur.fetchall()
        return [_metadata_credencial_azure(linha) for linha in linhas]
    finally:
        conn.close()


def salvar_credencial_azure_usuario(
    user_id: int,
    usuario_email: str,
    credencial_json: dict,
    substituir: bool,
) -> tuple[str, dict | None]:
    cifrado = criptografar(json.dumps(credencial_json))
    conn = conectar_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id
                FROM cloud_credentials
                WHERE user_id = %s AND provider = 'azure'
                FOR UPDATE
                """,
                (user_id,),
            )
            existente = cur.fetchone()
            if existente and not substituir:
                conn.rollback()
                return "exists", None
            if not existente and substituir:
                conn.rollback()
                return "missing", None

            if substituir:
                cur.execute(
                    """
                    UPDATE cloud_credentials
                    SET credencial_cifrada = %s, criado_em = now()
                    WHERE user_id = %s AND provider = 'azure'
                    RETURNING id, credencial_cifrada, criado_em
                    """,
                    (cifrado, user_id),
                )
                acao = "CREDENCIAL_SUBSTITUIDA"
            else:
                cur.execute(
                    """
                    INSERT INTO cloud_credentials (user_id, provider, credencial_cifrada)
                    VALUES (%s, 'azure', %s)
                    RETURNING id, credencial_cifrada, criado_em
                    """,
                    (user_id, cifrado),
                )
                acao = "CREDENCIAL_CADASTRADA"

            linha = cur.fetchone()
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider)
                VALUES (%s, %s, 'azure')
                """,
                (usuario_email, acao),
            )
        conn.commit()
        return "ok", _metadata_credencial_azure(linha)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def excluir_credencial_azure_usuario(user_id: int, usuario_email: str) -> bool:
    conn = conectar_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM cloud_credentials
                WHERE user_id = %s AND provider = 'azure'
                FOR UPDATE
                """,
                (user_id,),
            )
            if not cur.fetchone():
                conn.rollback()
                return False
            cur.execute(
                """
                DELETE FROM cloud_credentials
                WHERE user_id = %s AND provider = 'azure'
                """,
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO audit_log (usuario, acao, provider)
                VALUES (%s, 'CREDENCIAL_EXCLUIDA', 'azure')
                """,
                (usuario_email,),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
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


@app.exception_handler(RequestValidationError)
async def sanitizar_erro_validacao(request: Request, erro: RequestValidationError):
    if request.url.path == "/credenciais/gcp":
        return JSONResponse(
            status_code=422,
            content={"detail": "Requisição de credencial GCP inválida"},
        )
    if request.url.path == "/credenciais/azure":
        return JSONResponse(
            status_code=422,
            content={"detail": "Requisição de credencial Azure inválida"},
        )
    if request.url.path in {"/me/plano", "/pix/solicitacao"}:
        return JSONResponse(
            status_code=422,
            content={"detail": "Requisição de atualização de plano inválida"},
        )
    return await request_validation_exception_handler(request, erro)

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
    full_name: str | None = Field(
        default=None,
        description="Campo oficial do contrato novo. Obrigatorio fora da compatibilidade legada temporaria.",
    )
    email: EmailStr
    senha: str
    plano: str = "gratuito"
    aceite_termos: bool
    aceite_privacidade: bool | None = Field(
        default=None,
        description="Campo oficial do contrato novo. Obrigatorio fora da compatibilidade legada temporaria.",
    )
    terms_version: str | None = Field(
        default=None,
        description="Versao oficial dos Termos no contrato novo.",
    )
    privacy_version: str | None = Field(
        default=None,
        description="Versao oficial da Privacidade no contrato novo.",
    )
    versao_termos: str | None = Field(
        default=None,
        description="Temporario: versao enviada apenas pelo contrato legado de cadastro.",
    )

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
    model_config = ConfigDict(extra="forbid")

    plano: str

class PlanoResponse(BaseModel):
    plano_anterior: str
    plano: str
    alterado: bool
    message: str

class ChangePasswordRequest(BaseModel):
    senha_atual: str
    nova_senha: str
    confirmacao_nova_senha: str

class ChangePasswordResponse(BaseModel):
    ok: bool
    message: str

class PixRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plano: str
    comprovante: str = Field(default="", max_length=4096)

class CredencialAWS(BaseModel):
    access_key_id: str
    secret_access_key: str

class CredencialAWSResponse(BaseModel):
    id: int
    provider: str
    access_key_id_masked: str
    secret_access_key_masked: str
    criado_em: datetime

class CredencialGCP(BaseModel):
    service_account_json: object | None = None

class CredencialGCPResponse(BaseModel):
    id: int
    provider: str
    project_id: str
    client_email_masked: str
    criado_em: datetime

class CredencialAzure(BaseModel):
    tenant_id: object | None = None
    client_id: object | None = None
    client_secret: object | None = None
    subscription_id: object | None = None

class CredencialAzureResponse(BaseModel):
    id: int
    provider: str
    tenant_id_masked: str
    client_id_masked: str
    subscription_id_masked: str
    criado_em: datetime

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
    campos_novos = (
        dados.full_name,
        dados.aceite_privacidade,
        dados.terms_version,
        dados.privacy_version,
    )
    contrato_novo = all(valor is not None for valor in campos_novos)
    contrato_legado = all(valor is None for valor in campos_novos)
    if not contrato_novo and not contrato_legado:
        raise HTTPException(
            status_code=400,
            detail="Contrato de cadastro incompleto: envie todos os campos novos ou somente o contrato legado",
        )

    full_name = dados.full_name.strip() if contrato_novo else None
    email = str(dados.email).strip().lower()
    if contrato_novo and dados.versao_termos is not None:
        raise HTTPException(status_code=400, detail="Nao combine campos dos contratos novo e legado")
    if contrato_novo and len(full_name) < 3:
        raise HTTPException(status_code=400, detail="O nome completo deve ter pelo menos 3 caracteres")
    if contrato_novo and len(full_name) > 150:
        raise HTTPException(status_code=400, detail="O nome completo deve ter no maximo 150 caracteres")
    if dados.plano not in PLANOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Plano invalido")
    if len(dados.senha) < 8:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 8 caracteres")
    if not dados.aceite_termos:
        raise HTTPException(status_code=400, detail="Aceite os Termos de Uso para criar a conta")
    if contrato_novo and not dados.aceite_privacidade:
        raise HTTPException(status_code=400, detail="Aceite a Política de Privacidade para criar a conta")
    if contrato_novo and dados.terms_version != VERSAO_TERMOS_ATUAL:
        raise HTTPException(status_code=400, detail="Versao dos Termos de Uso invalida")
    if contrato_novo and dados.privacy_version != VERSAO_PRIVACIDADE_ATUAL:
        raise HTTPException(status_code=400, detail="Versao da Política de Privacidade invalida")
    if contrato_legado and dados.versao_termos != VERSAO_LEGADA_CADASTRO:
        raise HTTPException(status_code=400, detail="Versao legada dos Termos de Uso invalida")
    if buscar_usuario_por_email(email):
        raise HTTPException(status_code=409, detail="Ja existe uma conta com esse e-mail")

    senha_hash = gerar_hash_senha(dados.senha)
    novo = criar_usuario(
        full_name,
        email,
        senha_hash,
        dados.aceite_termos,
        dados.aceite_privacidade if contrato_novo else True,
        dados.terms_version if contrato_novo else dados.versao_termos,
        dados.privacy_version if contrato_novo else dados.versao_termos,
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

@app.post("/me/change-password", response_model=ChangePasswordResponse)
def alterar_minha_senha(dados: ChangePasswordRequest, usuario=Depends(usuario_atual)):
    if not dados.senha_atual:
        raise HTTPException(status_code=400, detail="Informe a senha atual")
    if not dados.nova_senha:
        raise HTTPException(status_code=400, detail="Informe a nova senha")
    if not dados.confirmacao_nova_senha:
        raise HTTPException(status_code=400, detail="Confirme a nova senha")
    if dados.nova_senha != dados.confirmacao_nova_senha:
        raise HTTPException(status_code=400, detail="A confirmação da nova senha não confere")
    if len(dados.nova_senha) < 8:
        raise HTTPException(status_code=400, detail="A nova senha deve ter pelo menos 8 caracteres")

    credencial = buscar_senha_hash_usuario(usuario["id"])
    if not credencial:
        raise HTTPException(status_code=401, detail="Token inválido")
    if not verificar_senha(dados.senha_atual, credencial["senha_hash"]):
        raise HTTPException(status_code=401, detail="Senha atual incorreta")
    if dados.nova_senha == dados.senha_atual:
        raise HTTPException(status_code=400, detail="A nova senha deve ser diferente da senha atual")

    novo_hash = gerar_hash_senha(dados.nova_senha)
    if not atualizar_senha_usuario(usuario["id"], novo_hash, usuario["email"]):
        raise HTTPException(status_code=401, detail="Token inválido")
    return {"ok": True, "message": "Senha alterada com sucesso."}

@app.get("/pix")
def dados_pix(usuario=Depends(usuario_atual)):
    return obter_config_pix()

@app.post("/pix/solicitacao")
def solicitar_ativacao_pix(dados: PixRequest, usuario=Depends(usuario_atual)):
    if dados.plano not in ("popular", "premium"):
        raise HTTPException(status_code=400, detail="Plano PIX inválido")
    try:
        status_solicitacao, solicitacao = criar_solicitacao_pix(
            usuario["id"], dados.plano, dados.comprovante
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Não foi possível registrar a solicitação de plano",
        ) from None
    if status_solicitacao == "missing_user":
        raise HTTPException(status_code=401, detail="Token inválido")
    if status_solicitacao == "already_active":
        raise HTTPException(status_code=409, detail="O plano solicitado já está ativo")
    if status_solicitacao == "pending":
        raise HTTPException(status_code=409, detail="Já existe uma solicitação de plano pendente")
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
    try:
        resultado = aprovar_solicitacao_pix(solicitacao_id, usuario["email"])
    except Exception:
        raise HTTPException(status_code=500, detail="Não foi possível aprovar a solicitação") from None
    if not resultado:
        raise HTTPException(status_code=404, detail="Solicitacao Pix pendente nao encontrada")
    if resultado == "invalid":
        raise HTTPException(status_code=409, detail="Solicitação de plano inconsistente")
    return resultado

@app.get("/me/plano/opcoes")
def opcoes_atualizacao_plano(usuario=Depends(usuario_atual)):
    return {
        "plano_atual": usuario["plano"],
        "opcoes": [
            {
                "plano": plano,
                "valor": PLANOS_VALORES[plano],
                "modo_ativacao": "direta" if plano == "gratuito" else "pix_aprovacao_manual",
            }
            for plano in PLANOS_VALIDOS
        ],
    }


@app.patch("/me/plano", response_model=PlanoResponse)
def atualizar_meu_plano(dados: PlanoRequest, usuario=Depends(usuario_atual)):
    if dados.plano not in PLANOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Plano inválido")
    try:
        atualizado = atualizar_plano_proprio(usuario["id"], dados.plano)
    except Exception:
        raise HTTPException(status_code=500, detail="Não foi possível atualizar o plano") from None
    if not atualizado:
        raise HTTPException(status_code=401, detail="Token inválido")
    if atualizado["bloqueado"]:
        raise HTTPException(
            status_code=403,
            detail="Planos pagos exigem solicitação PIX e aprovação manual",
        )
    return {
        "plano_anterior": atualizado["plano_anterior"],
        "plano": atualizado["plano"],
        "alterado": atualizado["alterado"],
        "message": (
            "Plano atualizado com sucesso."
            if atualizado["alterado"]
            else "O plano informado já está ativo."
        ),
    }

# ── Rotas de gerenciamento de credenciais de nuvem ────────────
def validar_credencial_aws(dados: CredencialAWS) -> dict:
    access_key_id = dados.access_key_id.strip()
    secret_access_key = dados.secret_access_key.strip()
    if not (16 <= len(access_key_id) <= 128) or not access_key_id.isalnum():
        raise HTTPException(status_code=400, detail="Access Key ID AWS inválida")
    if not (32 <= len(secret_access_key) <= 128):
        raise HTTPException(status_code=400, detail="Secret Access Key AWS inválida")
    return {
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
    }


def validar_credencial_gcp(dados: CredencialGCP) -> dict:
    service_account_json = dados.service_account_json
    if not isinstance(service_account_json, str) or not service_account_json.strip():
        raise HTTPException(status_code=400, detail="JSON da credencial GCP inválido")
    if len(service_account_json) > 65536:
        raise HTTPException(status_code=400, detail="JSON da credencial GCP inválido")
    try:
        info = json.loads(service_account_json)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="JSON da credencial GCP inválido") from None
    if not isinstance(info, dict):
        raise HTTPException(status_code=400, detail="JSON da credencial GCP inválido")
    if info.get("type") != "service_account":
        raise HTTPException(status_code=400, detail="Credencial GCP deve ser do tipo service_account")
    for campo in ("project_id", "client_email", "private_key"):
        if not isinstance(info.get(campo), str) or not info[campo].strip():
            raise HTTPException(status_code=400, detail=f"Credencial GCP sem o campo obrigatório {campo}")
    service_account_normalizada = json.dumps(info, ensure_ascii=False, separators=(",", ":"))
    return {"service_account_json": service_account_normalizada}


def _normalizar_uuid_azure(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip() or len(valor) > 64:
        raise HTTPException(status_code=400, detail=f"{campo} Azure inválido")
    try:
        identificador = UUID(valor.strip())
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"{campo} Azure inválido") from None
    return str(identificador)


def validar_credencial_azure(dados: CredencialAzure) -> dict:
    client_secret = dados.client_secret
    if not isinstance(client_secret, str) or not client_secret.strip() or len(client_secret) > 4096:
        raise HTTPException(status_code=400, detail="Client Secret Azure inválido")
    return {
        "tenant_id": _normalizar_uuid_azure(dados.tenant_id, "Tenant ID"),
        "client_id": _normalizar_uuid_azure(dados.client_id, "Client ID"),
        "client_secret": client_secret.strip(),
        "subscription_id": _normalizar_uuid_azure(dados.subscription_id, "Subscription ID"),
    }


def erro_interno_credencial_azure() -> HTTPException:
    return HTTPException(status_code=500, detail="Não foi possível processar a credencial Azure")

@app.get("/credenciais/aws", response_model=list[CredencialAWSResponse])
def listar_credenciais_aws(usuario=Depends(usuario_atual)):
    return listar_credenciais_aws_usuario(usuario["id"])

@app.post("/credenciais/aws", response_model=CredencialAWSResponse)
def cadastrar_credencial_aws(dados: CredencialAWS, usuario=Depends(usuario_atual)):
    status_salvamento, credencial = salvar_credencial_aws_usuario(
        usuario["id"],
        usuario["email"],
        validar_credencial_aws(dados),
        substituir=False,
    )
    if status_salvamento == "exists":
        raise HTTPException(
            status_code=409,
            detail="Já existe uma credencial AWS cadastrada; use a opção substituir",
        )
    return credencial

@app.put("/credenciais/aws", response_model=CredencialAWSResponse)
def substituir_credencial_aws(dados: CredencialAWS, usuario=Depends(usuario_atual)):
    status_salvamento, credencial = salvar_credencial_aws_usuario(
        usuario["id"],
        usuario["email"],
        validar_credencial_aws(dados),
        substituir=True,
    )
    if status_salvamento == "missing":
        raise HTTPException(status_code=404, detail="Credencial AWS não encontrada")
    return credencial

@app.delete("/credenciais/aws")
def excluir_credencial_aws(usuario=Depends(usuario_atual)):
    if not excluir_credencial_aws_usuario(usuario["id"], usuario["email"]):
        raise HTTPException(status_code=404, detail="Credencial AWS não encontrada")
    return {"ok": True, "message": "Credencial AWS excluída com sucesso."}

@app.get("/credenciais/gcp", response_model=list[CredencialGCPResponse])
def listar_credenciais_gcp(usuario=Depends(usuario_atual)):
    return listar_credenciais_gcp_usuario(usuario["id"])


@app.post("/credenciais/gcp", response_model=CredencialGCPResponse)
def cadastrar_credencial_gcp(dados: CredencialGCP, usuario=Depends(usuario_atual)):
    status_salvamento, credencial = salvar_credencial_gcp_usuario(
        usuario["id"],
        usuario["email"],
        validar_credencial_gcp(dados),
        substituir=False,
    )
    if status_salvamento == "exists":
        raise HTTPException(
            status_code=409,
            detail="Já existe uma credencial GCP cadastrada; use a opção substituir",
        )
    return credencial


@app.put("/credenciais/gcp", response_model=CredencialGCPResponse)
def substituir_credencial_gcp(dados: CredencialGCP, usuario=Depends(usuario_atual)):
    status_salvamento, credencial = salvar_credencial_gcp_usuario(
        usuario["id"],
        usuario["email"],
        validar_credencial_gcp(dados),
        substituir=True,
    )
    if status_salvamento == "missing":
        raise HTTPException(status_code=404, detail="Credencial GCP não encontrada")
    return credencial


@app.delete("/credenciais/gcp")
def excluir_credencial_gcp(usuario=Depends(usuario_atual)):
    if not excluir_credencial_gcp_usuario(usuario["id"], usuario["email"]):
        raise HTTPException(status_code=404, detail="Credencial GCP não encontrada")
    return {"ok": True, "message": "Credencial GCP excluída com sucesso."}

@app.get("/credenciais/azure", response_model=list[CredencialAzureResponse])
def listar_credenciais_azure(usuario=Depends(usuario_atual)):
    try:
        return listar_credenciais_azure_usuario(usuario["id"])
    except HTTPException:
        raise
    except Exception:
        raise erro_interno_credencial_azure() from None


@app.post("/credenciais/azure", response_model=CredencialAzureResponse)
def cadastrar_credencial_azure(dados: CredencialAzure, usuario=Depends(usuario_atual)):
    try:
        status_salvamento, credencial = salvar_credencial_azure_usuario(
            usuario["id"],
            usuario["email"],
            validar_credencial_azure(dados),
            substituir=False,
        )
        if status_salvamento == "exists":
            raise HTTPException(
                status_code=409,
                detail="Já existe uma credencial Azure cadastrada; use a opção substituir",
            )
        return credencial
    except HTTPException:
        raise
    except Exception:
        raise erro_interno_credencial_azure() from None


@app.put("/credenciais/azure", response_model=CredencialAzureResponse)
def substituir_credencial_azure(dados: CredencialAzure, usuario=Depends(usuario_atual)):
    try:
        status_salvamento, credencial = salvar_credencial_azure_usuario(
            usuario["id"],
            usuario["email"],
            validar_credencial_azure(dados),
            substituir=True,
        )
        if status_salvamento == "missing":
            raise HTTPException(status_code=404, detail="Credencial Azure não encontrada")
        return credencial
    except HTTPException:
        raise
    except Exception:
        raise erro_interno_credencial_azure() from None


@app.delete("/credenciais/azure")
def excluir_credencial_azure(usuario=Depends(usuario_atual)):
    try:
        if not excluir_credencial_azure_usuario(usuario["id"], usuario["email"]):
            raise HTTPException(status_code=404, detail="Credencial Azure não encontrada")
        return {"ok": True, "message": "Credencial Azure excluída com sucesso."}
    except HTTPException:
        raise
    except Exception:
        raise erro_interno_credencial_azure() from None

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

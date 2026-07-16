import os
import sys
import threading
import types
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import pydantic
from fastapi import HTTPException
from starlette.requests import Request


os.environ.setdefault("NANO_IAAS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "test-encryption-key")

try:
    import email_validator  # noqa: F401
except ModuleNotFoundError:
    pydantic.EmailStr = str

try:
    import psycopg2  # noqa: F401
except ModuleNotFoundError:
    psycopg2_module = types.ModuleType("psycopg2")
    extras_module = types.ModuleType("psycopg2.extras")
    extras_module.RealDictCursor = object
    psycopg2_module.extras = extras_module
    sys.modules["psycopg2"] = psycopg2_module
    sys.modules["psycopg2.extras"] = extras_module

from web.backend import main as backend


class FakeDatabase:
    def __init__(self):
        self.now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        self.rows = {}
        self.lock = threading.RLock()
        self.queries = []

    def connect(self):
        return FakeConnection(self)

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class FakeConnection:
    def __init__(self, database):
        self.database = database
        self.active = True
        self.database.lock.acquire()

    def cursor(self, *args, **kwargs):
        return FakeCursor(self.database)

    def commit(self):
        self._release()

    def rollback(self):
        self._release()

    def close(self):
        self._release()

    def _release(self):
        if self.active:
            self.active = False
            self.database.lock.release()


class FakeCursor:
    def __init__(self, database):
        self.database = database
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        sql = " ".join(query.split()).upper()
        params = params or ()
        self.database.queries.append(sql)

        if sql.startswith("SELECT NOW()"):
            self.result = (self.database.now,)
            return

        if sql.startswith("INSERT INTO LOGIN_ATTEMPTS"):
            attempt_key, scope, window_started_at, updated_at = params
            self.database.rows.setdefault(
                attempt_key,
                {
                    "scope": scope,
                    "failure_count": 0,
                    "window_started_at": window_started_at,
                    "blocked_until": None,
                    "updated_at": updated_at,
                },
            )
            self.result = None
            return

        if "FROM LOGIN_ATTEMPTS" in sql and "FOR UPDATE" in sql:
            attempt_key = params[0]
            row = self.database.rows.get(attempt_key)
            self.result = None if row is None else (
                row["failure_count"],
                row["window_started_at"],
                row["blocked_until"],
            )
            return

        if sql.startswith("UPDATE LOGIN_ATTEMPTS") and "SET FAILURE_COUNT = 0" in sql:
            window_started_at, updated_at, attempt_key = params
            row = self.database.rows[attempt_key]
            row.update(
                failure_count=0,
                window_started_at=window_started_at,
                blocked_until=None,
                updated_at=updated_at,
            )
            self.result = None
            return

        if sql.startswith("UPDATE LOGIN_ATTEMPTS"):
            failure_count, window_started_at, blocked_until, updated_at, attempt_key = params
            row = self.database.rows[attempt_key]
            row.update(
                failure_count=failure_count,
                window_started_at=window_started_at,
                blocked_until=blocked_until,
                updated_at=updated_at,
            )
            self.result = None
            return

        if sql.startswith("DELETE FROM LOGIN_ATTEMPTS WHERE ATTEMPT_KEY = ANY"):
            for attempt_key in params[0]:
                self.database.rows.pop(attempt_key, None)
            self.result = None
            return

        if sql.startswith("WITH EXPIRADOS AS"):
            retention_seconds = params[0]
            cutoff = self.database.now - timedelta(seconds=retention_seconds)
            expired = sorted(
                (
                    (key, row)
                    for key, row in self.database.rows.items()
                    if row["updated_at"] < cutoff
                ),
                key=lambda item: item[1]["updated_at"],
            )[:100]
            for key, _ in expired:
                self.database.rows.pop(key, None)
            self.result = None
            return

        raise AssertionError(f"SQL nao suportado pelo banco de teste: {sql}")

    def fetchone(self):
        return self.result


def make_request(ip="203.0.113.10", forwarded_for=None):
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/login",
            "query_string": b"",
            "headers": headers,
            "client": (ip, 12345),
            "server": ("api.nano-iaas.com.br", 443),
        }
    )


def make_form(username="user@example.com", password="wrong-password"):
    return SimpleNamespace(username=username, password=password)


@pytest.fixture
def rate_limit(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(backend, "conectar_db", database.connect)
    monkeypatch.setattr(backend, "obter_chave_rate_limit", lambda: b"test-rate-limit-key")
    monkeypatch.setattr(backend, "limpar_tentativas_login_expiradas", lambda: None)
    monkeypatch.setattr(backend, "LOGIN_RATE_LIMIT_ACCOUNT_MAX_ATTEMPTS", 10)
    monkeypatch.setattr(backend, "LOGIN_RATE_LIMIT_ACCOUNT_IP_MAX_ATTEMPTS", 5)
    monkeypatch.setattr(backend, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 300)
    monkeypatch.setattr(backend, "LOGIN_RATE_LIMIT_BLOCK_SECONDS", 900)
    return database


def configure_invalid_user(monkeypatch):
    monkeypatch.setattr(
        backend,
        "buscar_usuario_por_email",
        lambda username: {
            "id": 1,
            "email": username,
            "senha_hash": "stored-hash",
        },
    )
    monkeypatch.setattr(backend, "verificar_senha", lambda password, password_hash: False)


def call_login(request=None, form=None):
    return backend.login(request or make_request(), form or make_form())


def test_valid_credentials_generate_token(rate_limit, monkeypatch):
    monkeypatch.setattr(
        backend,
        "buscar_usuario_por_email",
        lambda username: {"id": 7, "email": username, "senha_hash": "stored-hash"},
    )
    monkeypatch.setattr(backend, "verificar_senha", lambda password, password_hash: True)
    monkeypatch.setattr(backend, "criar_token", lambda payload: "signed-token")

    result = call_login(form=make_form(password="correct-password"))

    assert result == {"access_token": "signed-token", "token_type": "bearer"}
    assert rate_limit.rows == {}


def test_invalid_password_returns_401(rate_limit, monkeypatch):
    configure_invalid_user(monkeypatch)

    with pytest.raises(HTTPException) as error:
        call_login()

    assert error.value.status_code == 401
    assert error.value.detail == "Usuario ou senha incorretos".replace("Usuario", "Usuário")


def test_unknown_user_has_same_response_and_uses_dummy_hash(rate_limit, monkeypatch):
    verified_hashes = []
    monkeypatch.setattr(backend, "buscar_usuario_por_email", lambda username: None)
    monkeypatch.setattr(
        backend,
        "verificar_senha",
        lambda password, password_hash: verified_hashes.append(password_hash) or False,
    )

    with pytest.raises(HTTPException) as error:
        call_login(form=make_form(username="missing@example.com"))

    assert error.value.status_code == 401
    assert error.value.detail == "Usuário ou senha incorretos"
    assert verified_hashes == [backend.HASH_SENHA_FICTICIA]


def test_fifth_failure_for_same_account_and_ip_returns_429(rate_limit, monkeypatch):
    configure_invalid_user(monkeypatch)

    for _ in range(4):
        with pytest.raises(HTTPException) as error:
            call_login()
        assert error.value.status_code == 401

    with pytest.raises(HTTPException) as error:
        call_login()

    assert error.value.status_code == 429
    assert int(error.value.headers["Retry-After"]) > 0


def test_blocked_attempt_skips_password_verification(rate_limit, monkeypatch):
    configure_invalid_user(monkeypatch)
    for _ in range(5):
        with pytest.raises(HTTPException):
            call_login()

    calls = []
    monkeypatch.setattr(
        backend,
        "verificar_senha",
        lambda password, password_hash: calls.append(password) or False,
    )
    with pytest.raises(HTTPException) as error:
        call_login()

    assert error.value.status_code == 429
    assert calls == []


def test_expired_block_allows_new_attempt(rate_limit, monkeypatch):
    configure_invalid_user(monkeypatch)
    for _ in range(5):
        with pytest.raises(HTTPException):
            call_login()

    rate_limit.advance(901)
    with pytest.raises(HTTPException) as error:
        call_login()

    assert error.value.status_code == 401


def test_successful_login_clears_both_scopes(rate_limit, monkeypatch):
    configure_invalid_user(monkeypatch)
    for _ in range(2):
        with pytest.raises(HTTPException):
            call_login()
    assert len(rate_limit.rows) == 2

    monkeypatch.setattr(backend, "verificar_senha", lambda password, password_hash: True)
    monkeypatch.setattr(backend, "criar_token", lambda payload: "token")
    call_login(form=make_form(password="correct"))

    assert rate_limit.rows == {}


def test_different_ips_share_account_limit(rate_limit, monkeypatch):
    configure_invalid_user(monkeypatch)
    monkeypatch.setattr(backend, "LOGIN_RATE_LIMIT_ACCOUNT_MAX_ATTEMPTS", 3)

    for ip in ("203.0.113.1", "203.0.113.2"):
        with pytest.raises(HTTPException) as error:
            call_login(request=make_request(ip=ip))
        assert error.value.status_code == 401

    with pytest.raises(HTTPException) as error:
        call_login(request=make_request(ip="203.0.113.3"))

    assert error.value.status_code == 429


def test_different_accounts_on_same_ip_do_not_share_global_limit(rate_limit, monkeypatch):
    configure_invalid_user(monkeypatch)

    for username in ("first@example.com", "second@example.com"):
        for _ in range(4):
            with pytest.raises(HTTPException) as error:
                call_login(form=make_form(username=username))
            assert error.value.status_code == 401


def test_proxy_header_is_ignored_when_disabled():
    request = make_request(ip="10.20.1.5", forwarded_for="198.51.100.10")
    assert backend.resolver_ip_cliente(request, confiar_proxy=False) == "10.20.1.5"


def test_first_valid_forwarded_ip_is_used_when_enabled():
    request = make_request(
        ip="10.20.1.5",
        forwarded_for="invalid, 198.51.100.10, 203.0.113.20",
    )
    assert backend.resolver_ip_cliente(request, confiar_proxy=True) == "198.51.100.10"


def test_invalid_forwarded_header_uses_client_fallback():
    request = make_request(ip="10.20.1.5", forwarded_for="invalid, also-invalid")
    assert backend.resolver_ip_cliente(request, confiar_proxy=True) == "10.20.1.5"


def test_concurrent_updates_do_not_lose_failures(rate_limit):
    keys = backend.gerar_chaves_rate_limit("user@example.com", "203.0.113.10")
    backend.LOGIN_RATE_LIMIT_ACCOUNT_MAX_ATTEMPTS = 100
    backend.LOGIN_RATE_LIMIT_ACCOUNT_IP_MAX_ATTEMPTS = 100

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: backend.registrar_falhas_login(keys), range(20)))

    assert {row["failure_count"] for row in rate_limit.rows.values()} == {20}
    assert any("FOR UPDATE" in query for query in rate_limit.queries)


def test_two_simulated_instances_share_database_state(rate_limit):
    keys = backend.gerar_chaves_rate_limit("user@example.com", "203.0.113.10")

    instance_a = backend.registrar_falhas_login
    instance_b = backend.registrar_falhas_login
    instance_a(keys)
    instance_b(keys)

    assert {row["failure_count"] for row in rate_limit.rows.values()} == {2}


def test_expired_window_restarts_counter(rate_limit):
    keys = backend.gerar_chaves_rate_limit("user@example.com", "203.0.113.10")
    backend.registrar_falhas_login(keys)
    backend.registrar_falhas_login(keys)
    rate_limit.advance(301)

    backend.registrar_falhas_login(keys)

    assert {row["failure_count"] for row in rate_limit.rows.values()} == {1}


def test_rate_limit_response_does_not_expose_sensitive_values(rate_limit, monkeypatch):
    configure_invalid_user(monkeypatch)
    username = "private@example.com"
    password = "do-not-expose"
    for _ in range(5):
        with pytest.raises(HTTPException) as error:
            call_login(form=make_form(username=username, password=password))

    public_response = f"{error.value.detail} {error.value.headers}"
    keys = backend.gerar_chaves_rate_limit(username, "203.0.113.10")
    assert username not in public_response
    assert password not in public_response
    assert "token" not in public_response.casefold()
    assert all(value not in public_response for value in keys.values())


def test_rate_limit_database_failure_is_closed(monkeypatch):
    monkeypatch.setattr(
        backend,
        "conectar_db",
        lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    monkeypatch.setattr(backend, "obter_chave_rate_limit", lambda: b"test-key")
    monkeypatch.setattr(backend, "limpar_tentativas_login_expiradas", lambda: None)
    password_checks = []
    monkeypatch.setattr(
        backend,
        "verificar_senha",
        lambda password, password_hash: password_checks.append(password) or False,
    )

    with pytest.raises(HTTPException) as error:
        call_login()

    assert error.value.status_code == 503
    assert password_checks == []


def test_cleanup_failure_does_not_block_login_maintenance(monkeypatch):
    monkeypatch.setattr(
        backend,
        "conectar_db",
        lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    monkeypatch.setattr(backend, "_ultima_limpeza_rate_limit", -1000.0)

    backend.limpar_tentativas_login_expiradas()


def test_hmac_keys_are_normalized_and_do_not_contain_username(monkeypatch):
    monkeypatch.setattr(backend, "obter_chave_rate_limit", lambda: b"test-key")

    first = backend.gerar_chaves_rate_limit(" User@Example.COM ", "203.0.113.10")
    second = backend.gerar_chaves_rate_limit("user@example.com", "203.0.113.10")

    assert first == second
    assert set(first) == {"account", "account_ip"}
    assert all(len(value) == 64 for value in first.values())
    assert all("user@example.com" not in value for value in first.values())


@pytest.mark.frontend_static
def test_frontend_handles_429_and_retry_after():
    html = (Path(__file__).parents[1] / "docs" / "index.html").read_text()

    assert "e.status === 429" in html
    assert "Retry-After" in html

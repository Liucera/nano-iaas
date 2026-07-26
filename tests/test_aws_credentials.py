import copy
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pydantic
from fastapi import HTTPException


os.environ.setdefault("NANO_IAAS_SECRET_KEY", "aws-credentials-test-secret")
os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "aws-credentials-test-encryption-key")
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


ACCESS_KEY_ONE = "TESTACCESSKEY000001"
SECRET_KEY_ONE = "fictitious-secret-material-000000000000"
ACCESS_KEY_TWO = "TESTACCESSKEY000002"
SECRET_KEY_TWO = "fictitious-secret-material-111111111111"
USER_ONE = {"id": 41, "email": "user-one@example.invalid"}
USER_TWO = {"id": 42, "email": "user-two@example.invalid"}


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.one = None
        self.all = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        state = self.connection.state

        def require(*fragments):
            for fragment in fragments:
                assert fragment in normalized, f"SQL sem trecho obrigatório: {fragment}"
        self.one = None
        self.all = []

        if normalized.startswith("SELECT id, credencial_cifrada, criado_em"):
            require("FROM cloud_credentials", "WHERE user_id = %s AND provider = 'aws'", "ORDER BY id")
            assert len(params) == 1
            user_id = params[0]
            record = state["credentials"].get(user_id)
            self.all = [copy.deepcopy(record)] if record else []
        elif normalized.startswith("SELECT id FROM cloud_credentials"):
            require("WHERE user_id = %s AND provider = 'aws'", "FOR UPDATE")
            assert len(params) == 1
            user_id = params[0]
            record = state["credentials"].get(user_id)
            self.one = {"id": record["id"]} if record else None
        elif normalized.startswith("INSERT INTO cloud_credentials"):
            require(
                "INSERT INTO cloud_credentials (user_id, provider, credencial_cifrada)",
                "VALUES (%s, 'aws', %s)",
                "RETURNING id, credencial_cifrada, criado_em",
            )
            assert len(params) == 2
            user_id, ciphertext = params
            record = {
                "id": 1000 + user_id,
                "credencial_cifrada": ciphertext,
                "criado_em": datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc),
            }
            state["credentials"][user_id] = record
            self.one = copy.deepcopy(record)
        elif normalized.startswith("UPDATE cloud_credentials"):
            require(
                "SET credencial_cifrada = %s, criado_em = now()",
                "WHERE user_id = %s AND provider = 'aws'",
                "RETURNING id, credencial_cifrada, criado_em",
            )
            assert len(params) == 2
            ciphertext, user_id = params
            record = state["credentials"][user_id]
            record["credencial_cifrada"] = ciphertext
            record["criado_em"] = datetime(2026, 7, 17, 13, 0, tzinfo=timezone.utc)
            self.one = copy.deepcopy(record)
        elif normalized.startswith("DELETE FROM cloud_credentials"):
            require("WHERE user_id = %s AND provider = 'aws'")
            assert len(params) == 1
            state["credentials"].pop(params[0], None)
        elif normalized.startswith("INSERT INTO audit_log"):
            require(
                "INSERT INTO audit_log (usuario, acao, provider)",
                "VALUES",
                "'aws'",
            )
            assert "credencial_cifrada" not in normalized
            if self.connection.fail_audit:
                raise RuntimeError("simulated audit failure")
            state["audits"].append({"query": normalized, "params": tuple(params)})
        else:
            raise AssertionError(f"SQL inesperado: {normalized}")

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.all


class FakeConnection:
    def __init__(self, state, fail_audit=False):
        self.state = state
        self.snapshot = copy.deepcopy(state)
        self.fail_audit = fail_audit
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, *_args, **_kwargs):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True
        self.state.clear()
        self.state.update(copy.deepcopy(self.snapshot))

    def close(self):
        self.closed = True


@pytest.fixture
def fake_database(monkeypatch):
    state = {"credentials": {}, "audits": []}
    connections = []

    def connect():
        connection = FakeConnection(state)
        connections.append(connection)
        return connection

    monkeypatch.setattr(backend, "conectar_db", connect)
    monkeypatch.setattr(
        backend,
        "validar_acesso_credencial_cloud",
        lambda _provider, _credential: None,
    )
    backend._fernet = None
    return state, connections


def aws_request(access_key=ACCESS_KEY_ONE, secret_key=SECRET_KEY_ONE):
    return backend.CredencialAWS(
        access_key_id=access_key,
        secret_access_key=secret_key,
    )


def serialized(value):
    return repr(value)


def test_absence_returns_empty_list_for_authenticated_user(fake_database):
    assert backend.listar_credenciais_aws(USER_ONE) == []


def test_create_encrypts_and_returns_only_masked_metadata(fake_database):
    state, connections = fake_database
    response = backend.cadastrar_credencial_aws(aws_request(), USER_ONE)

    ciphertext = state["credentials"][USER_ONE["id"]]["credencial_cifrada"]
    assert ACCESS_KEY_ONE not in ciphertext
    assert SECRET_KEY_ONE not in ciphertext
    assert backend.descriptografar(ciphertext)
    assert response["provider"] == "aws"
    assert response["access_key_id_masked"] == "TEST***********0001"
    assert response["secret_access_key_masked"] == "********0000"
    assert ACCESS_KEY_ONE not in serialized(response)
    assert SECRET_KEY_ONE not in serialized(response)
    assert connections[-1].committed is True


def test_list_is_scoped_exclusively_to_token_user(fake_database):
    backend.cadastrar_credencial_aws(aws_request(), USER_ONE)
    backend.cadastrar_credencial_aws(
        aws_request(ACCESS_KEY_TWO, SECRET_KEY_TWO),
        USER_TWO,
    )

    first = backend.listar_credenciais_aws(USER_ONE)
    second = backend.listar_credenciais_aws(USER_TWO)

    assert len(first) == len(second) == 1
    assert first[0]["access_key_id_masked"].endswith("0001")
    assert second[0]["access_key_id_masked"].endswith("0002")
    assert ACCESS_KEY_TWO not in serialized(first)
    assert SECRET_KEY_TWO not in serialized(first)


def test_duplicate_create_requires_explicit_replace(fake_database):
    backend.cadastrar_credencial_aws(aws_request(), USER_ONE)

    with pytest.raises(HTTPException) as error:
        backend.cadastrar_credencial_aws(
            aws_request(ACCESS_KEY_TWO, SECRET_KEY_TWO),
            USER_ONE,
        )

    assert error.value.status_code == 409
    current = backend.listar_credenciais_aws(USER_ONE)[0]
    assert current["access_key_id_masked"].endswith("0001")


def test_replace_is_transactional_and_does_not_change_other_user(fake_database):
    backend.cadastrar_credencial_aws(aws_request(), USER_ONE)
    backend.cadastrar_credencial_aws(
        aws_request(ACCESS_KEY_TWO, SECRET_KEY_TWO),
        USER_TWO,
    )

    response = backend.substituir_credencial_aws(
        aws_request("REPLACEDACCESS00001", "replacement-secret-material-222222222222"),
        USER_ONE,
    )

    assert response["access_key_id_masked"].endswith("0001")
    other = backend.listar_credenciais_aws(USER_TWO)[0]
    assert other["access_key_id_masked"].endswith("0002")


def test_replace_missing_credential_returns_404(fake_database):
    with pytest.raises(HTTPException) as error:
        backend.substituir_credencial_aws(aws_request(), USER_ONE)
    assert error.value.status_code == 404


def test_delete_only_removes_authenticated_users_credential(fake_database):
    backend.cadastrar_credencial_aws(aws_request(), USER_ONE)
    backend.cadastrar_credencial_aws(
        aws_request(ACCESS_KEY_TWO, SECRET_KEY_TWO),
        USER_TWO,
    )

    response = backend.excluir_credencial_aws(USER_ONE)

    assert response["ok"] is True
    assert backend.listar_credenciais_aws(USER_ONE) == []
    assert len(backend.listar_credenciais_aws(USER_TWO)) == 1


def test_delete_missing_credential_returns_404(fake_database):
    with pytest.raises(HTTPException) as error:
        backend.excluir_credencial_aws(USER_ONE)
    assert error.value.status_code == 404


def test_audit_contains_action_user_provider_and_no_credentials(fake_database):
    state, _ = fake_database
    backend.cadastrar_credencial_aws(aws_request(), USER_ONE)
    backend.substituir_credencial_aws(
        aws_request(ACCESS_KEY_TWO, SECRET_KEY_TWO),
        USER_ONE,
    )
    backend.excluir_credencial_aws(USER_ONE)

    audit = serialized(state["audits"])
    assert USER_ONE["email"] in audit
    assert "CREDENCIAL_CADASTRADA" in audit
    assert "CREDENCIAL_SUBSTITUIDA" in audit
    assert "INSERT INTO audit_log (usuario, acao, provider)" in audit
    assert "'aws'" in audit
    for sensitive in (ACCESS_KEY_ONE, SECRET_KEY_ONE, ACCESS_KEY_TWO, SECRET_KEY_TWO):
        assert sensitive not in audit


def test_audit_failure_rolls_back_replacement(monkeypatch):
    monkeypatch.setattr(
        backend,
        "validar_acesso_credencial_cloud",
        lambda _provider, _credential: None,
    )
    state = {"credentials": {}, "audits": []}
    monkeypatch.setattr(backend, "conectar_db", lambda: FakeConnection(state))
    backend.cadastrar_credencial_aws(aws_request(), USER_ONE)
    original = copy.deepcopy(state["credentials"][USER_ONE["id"]])

    failed_connection = FakeConnection(state, fail_audit=True)
    monkeypatch.setattr(backend, "conectar_db", lambda: failed_connection)
    with pytest.raises(RuntimeError, match="simulated audit failure"):
        backend.substituir_credencial_aws(
            aws_request(ACCESS_KEY_TWO, SECRET_KEY_TWO),
            USER_ONE,
        )

    assert failed_connection.rolled_back is True
    assert state["credentials"][USER_ONE["id"]] == original


@pytest.mark.parametrize(
    ("access_key", "secret_key", "detail"),
    [
        ("short", SECRET_KEY_ONE, "Access Key ID AWS inválida"),
        ("INVALID-ACCESS-KEY!", SECRET_KEY_ONE, "Access Key ID AWS inválida"),
        (ACCESS_KEY_ONE, "short", "Secret Access Key AWS inválida"),
    ],
)
def test_validation_errors_do_not_echo_credentials(access_key, secret_key, detail):
    with pytest.raises(HTTPException) as error:
        backend.validar_credencial_aws(aws_request(access_key, secret_key))
    assert error.value.status_code == 400
    assert error.value.detail == detail
    assert access_key not in error.value.detail
    assert secret_key not in error.value.detail


def test_schema_and_sql_contract_match_real_cloud_credentials_table():
    source = Path(backend.__file__).read_text()
    schema = source[
        source.index("CREATE TABLE IF NOT EXISTS cloud_credentials"):
        source.index("CREATE TABLE IF NOT EXISTS pix_payment_requests")
    ]
    assert "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE" in schema
    assert "provider TEXT NOT NULL" in schema
    assert "credencial_cifrada TEXT NOT NULL" in schema
    assert "criado_em TIMESTAMPTZ NOT NULL DEFAULT now()" in schema
    assert "UNIQUE(user_id, provider)" in schema


def test_audit_failure_rolls_back_creation(monkeypatch):
    monkeypatch.setattr(
        backend,
        "validar_acesso_credencial_cloud",
        lambda _provider, _credential: None,
    )
    state = {"credentials": {}, "audits": []}
    failed_connection = FakeConnection(state, fail_audit=True)
    monkeypatch.setattr(backend, "conectar_db", lambda: failed_connection)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        backend.cadastrar_credencial_aws(aws_request(), USER_ONE)

    assert failed_connection.rolled_back is True
    assert state == {"credentials": {}, "audits": []}


def test_legacy_aws_auth_error_does_not_log_credentials(monkeypatch):
    def fail_session(**_kwargs):
        raise RuntimeError(f"{ACCESS_KEY_ONE} {SECRET_KEY_ONE}")

    from unittest.mock import Mock

    captured_logger = Mock()
    monkeypatch.setattr("providers.aws.s3_reader.boto3.Session", fail_session)
    monkeypatch.setattr("providers.aws.s3_reader.logger", captured_logger)
    reader = backend.S3Reader()

    assert reader.authenticate({
        "access_key_id": ACCESS_KEY_ONE,
        "secret_access_key": SECRET_KEY_ONE,
    }) is False

    captured_logger.warning.assert_called_once_with(
        "provider_authentication_failed",
        extra={
            "provider": "aws",
            "operation": "authenticate",
        },
    )
    output = repr(captured_logger.mock_calls)
    assert ACCESS_KEY_ONE not in output
    assert SECRET_KEY_ONE not in output


@pytest.mark.parametrize("operation", ["list", "read"])
def test_legacy_aws_client_errors_do_not_log_credentials(operation, monkeypatch):
    sensitive_error = backend.ClientError(
        {
            "Error": {
                "Code": "AccessDenied",
                "Message": f"{ACCESS_KEY_ONE} {SECRET_KEY_ONE}",
            }
        },
        "SensitiveOperation",
    )

    class FailingClient:
        def list_buckets(self):
            raise sensitive_error

        def get_paginator(self, _name):
            raise sensitive_error

    from unittest.mock import Mock

    captured_logger = Mock()
    monkeypatch.setattr("providers.aws.s3_reader.logger", captured_logger)

    reader = backend.S3Reader()
    reader.client = FailingClient()
    if operation == "list":
        assert list(reader.list_resources()) == []
    else:
        assert list(reader.read("s3://fictitious-bucket/dados/")) == []

    expected_event = (
        "provider_list_failed"
        if operation == "list"
        else "provider_read_failed"
    )
    expected_operation = (
        "list_resources"
        if operation == "list"
        else "read"
    )
    captured_logger.error.assert_called_once_with(
        expected_event,
        extra={
            "provider": "aws",
            "operation": expected_operation,
        },
    )
    output = repr(captured_logger.mock_calls)
    assert ACCESS_KEY_ONE not in output
    assert SECRET_KEY_ONE not in output

def test_all_aws_credential_routes_require_bearer_authentication():
    schema = backend.app.openapi()
    for method in ("get", "post", "put", "delete"):
        operation = schema["paths"]["/credenciais/aws"][method]
        assert operation["security"] == [{"OAuth2PasswordBearer": []}]


def test_provider_rejects_failed_aws_authentication(monkeypatch):
    class FailingS3Reader:
        def authenticate(self, _profile):
            return False

    monkeypatch.setattr(
        backend,
        "buscar_credencial",
        lambda _user_id, _provider: {
            "access_key_id": ACCESS_KEY_ONE,
            "secret_access_key": SECRET_KEY_ONE,
        },
    )
    monkeypatch.setattr(backend, "S3Reader", FailingS3Reader)

    user = {
        "id": USER_ONE["id"],
        "email": USER_ONE["email"],
        "is_admin": False,
    }

    with pytest.raises(
        ValueError,
        match="Falha ao autenticar na AWS com as credenciais fornecidas",
    ):
        backend.obter_provider_autenticado("aws", user)


def test_admin_fallback_rejects_failed_aws_authentication(monkeypatch):
    class FailingS3Reader:
        def __init__(self, **_kwargs):
            pass

        def authenticate(self, _profile):
            return False

    monkeypatch.setattr(
        backend,
        "buscar_credencial",
        lambda _user_id, _provider: None,
    )
    monkeypatch.setattr(backend, "S3Reader", FailingS3Reader)
    monkeypatch.setenv(
        "NANO_IAAS_S3_ALLOWED_BUCKETS",
        "nano-iaas-raw-dev",
    )

    user = {
        "id": USER_ONE["id"],
        "email": USER_ONE["email"],
        "is_admin": True,
    }

    with pytest.raises(
        ValueError,
        match="Falha ao autenticar na AWS com as credenciais fornecidas",
    ):
        backend.obter_provider_autenticado("aws", user)

import asyncio
import copy
import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pydantic
from azure.core.exceptions import AzureError
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

os.environ.setdefault("NANO_IAAS_SECRET_KEY", "azure-credentials-test-secret")
os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "azure-credentials-test-encryption-key")
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

from providers.azure.blob_reader import BlobReader
from web.backend import main as backend


TENANT_ONE = "11111111-1111-4111-8111-111111111111"
CLIENT_ONE = "22222222-2222-4222-8222-222222222222"
SUBSCRIPTION_ONE = "33333333-3333-4333-8333-333333333333"
SECRET_ONE = "fictitious-client-secret-material-one"
TENANT_TWO = "44444444-4444-4444-8444-444444444444"
CLIENT_TWO = "55555555-5555-4555-8555-555555555555"
SUBSCRIPTION_TWO = "66666666-6666-4666-8666-666666666666"
SECRET_TWO = "fictitious-client-secret-material-two"
USER_ONE = {"id": 71, "email": "azure-one@example.invalid"}
USER_TWO = {"id": 72, "email": "azure-two@example.invalid"}


def azure_request(tenant=TENANT_ONE, client=CLIENT_ONE, secret=SECRET_ONE, subscription=SUBSCRIPTION_ONE):
    return backend.CredencialAzure(
        tenant_id=tenant,
        client_id=client,
        client_secret=secret,
        subscription_id=subscription,
    )


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
        sql = " ".join(query.split())
        state = self.connection.state
        self.one, self.all = None, []
        if sql.startswith("SELECT id, credencial_cifrada, criado_em"):
            assert "WHERE user_id = %s AND provider = 'azure'" in sql
            record = state["credentials"].get(params[0])
            self.all = [copy.deepcopy(record)] if record else []
        elif sql.startswith("SELECT id FROM cloud_credentials"):
            assert "WHERE user_id = %s AND provider = 'azure' FOR UPDATE" in sql
            record = state["credentials"].get(params[0])
            self.one = {"id": record["id"]} if record else None
        elif sql.startswith("INSERT INTO cloud_credentials"):
            assert "VALUES (%s, 'azure', %s)" in sql
            user_id, ciphertext = params
            record = {
                "id": 3000 + user_id,
                "credencial_cifrada": ciphertext,
                "criado_em": datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
            }
            state["credentials"][user_id] = record
            self.one = copy.deepcopy(record)
        elif sql.startswith("UPDATE cloud_credentials"):
            assert "WHERE user_id = %s AND provider = 'azure'" in sql
            ciphertext, user_id = params
            record = state["credentials"][user_id]
            record["credencial_cifrada"] = ciphertext
            self.one = copy.deepcopy(record)
        elif sql.startswith("DELETE FROM cloud_credentials"):
            assert "WHERE user_id = %s AND provider = 'azure'" in sql
            state["credentials"].pop(params[0], None)
        elif sql.startswith("INSERT INTO audit_log"):
            assert "INSERT INTO audit_log (usuario, acao, provider)" in sql
            assert "'azure'" in sql
            if self.connection.fail_audit:
                raise RuntimeError("simulated audit failure")
            state["audits"].append({"query": sql, "params": tuple(params)})
        else:
            raise AssertionError(f"SQL inesperado: {sql}")

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.all


class FakeConnection:
    def __init__(self, state, fail_audit=False):
        self.state = state
        self.snapshot = copy.deepcopy(state)
        self.fail_audit = fail_audit
        self.committed = self.rolled_back = False

    def cursor(self, *_args, **_kwargs):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True
        self.state.clear()
        self.state.update(copy.deepcopy(self.snapshot))

    def close(self):
        pass


@pytest.fixture
def fake_database(monkeypatch):
    state = {"credentials": {}, "audits": []}
    monkeypatch.setattr(backend, "conectar_db", lambda: FakeConnection(state))
    backend._fernet = None
    return state


def test_empty_list_and_full_crud_are_scoped_to_token_user(fake_database):
    state = fake_database
    assert backend.listar_credenciais_azure(USER_ONE) == []
    created = backend.cadastrar_credencial_azure(azure_request(), USER_ONE)
    backend.cadastrar_credencial_azure(
        azure_request(TENANT_TWO, CLIENT_TWO, SECRET_TWO, SUBSCRIPTION_TWO), USER_TWO
    )
    assert created["tenant_id_masked"].startswith("1111")
    assert created["client_id_masked"].endswith("2222")
    assert created["subscription_id_masked"].endswith("3333")
    assert SECRET_ONE not in repr(created)
    ciphertext = state["credentials"][USER_ONE["id"]]["credencial_cifrada"]
    for value in (TENANT_ONE, CLIENT_ONE, SECRET_ONE, SUBSCRIPTION_ONE):
        assert value not in ciphertext
    stored = json.loads(backend.descriptografar(ciphertext))
    assert stored == {
        "tenant_id": TENANT_ONE,
        "client_id": CLIENT_ONE,
        "client_secret": SECRET_ONE,
        "subscription_id": SUBSCRIPTION_ONE,
    }
    replaced = backend.substituir_credencial_azure(
        azure_request(TENANT_TWO, CLIENT_TWO, SECRET_TWO, SUBSCRIPTION_TWO), USER_ONE
    )
    assert replaced["tenant_id_masked"].startswith("4444")
    assert backend.listar_credenciais_azure(USER_TWO)[0]["tenant_id_masked"].startswith("4444")
    assert backend.excluir_credencial_azure(USER_ONE)["ok"] is True
    assert backend.listar_credenciais_azure(USER_ONE) == []
    assert len(backend.listar_credenciais_azure(USER_TWO)) == 1


def test_duplicate_and_missing_operations_are_explicit(fake_database):
    backend.cadastrar_credencial_azure(azure_request(), USER_ONE)
    with pytest.raises(HTTPException) as duplicate:
        backend.cadastrar_credencial_azure(azure_request(), USER_ONE)
    assert duplicate.value.status_code == 409
    with pytest.raises(HTTPException) as missing_replace:
        backend.substituir_credencial_azure(azure_request(), USER_TWO)
    assert missing_replace.value.status_code == 404
    with pytest.raises(HTTPException) as missing_delete:
        backend.excluir_credencial_azure(USER_TWO)
    assert missing_delete.value.status_code == 404


def test_audit_has_only_action_user_provider_and_no_credentials(fake_database):
    state = fake_database
    backend.cadastrar_credencial_azure(azure_request(), USER_ONE)
    backend.substituir_credencial_azure(
        azure_request(TENANT_TWO, CLIENT_TWO, SECRET_TWO, SUBSCRIPTION_TWO), USER_ONE
    )
    backend.excluir_credencial_azure(USER_ONE)
    audit = repr(state["audits"])
    for action in ("CREDENCIAL_CADASTRADA", "CREDENCIAL_SUBSTITUIDA", "CREDENCIAL_EXCLUIDA"):
        assert action in audit
    for value in (TENANT_ONE, CLIENT_ONE, SECRET_ONE, SUBSCRIPTION_ONE, SECRET_TWO):
        assert value not in audit


@pytest.mark.parametrize("operation", ["create", "replace", "delete"])
def test_audit_failure_rolls_back_same_transaction(monkeypatch, operation):
    state = {"credentials": {}, "audits": []}
    monkeypatch.setattr(backend, "conectar_db", lambda: FakeConnection(state))
    backend._fernet = None
    if operation != "create":
        backend.salvar_credencial_azure_usuario(
            USER_ONE["id"], USER_ONE["email"], backend.validar_credencial_azure(azure_request()), False
        )
    original = copy.deepcopy(state)
    failed = FakeConnection(state, fail_audit=True)
    monkeypatch.setattr(backend, "conectar_db", lambda: failed)
    with pytest.raises(RuntimeError, match="simulated audit failure"):
        if operation == "create":
            backend.salvar_credencial_azure_usuario(
                USER_ONE["id"], USER_ONE["email"], backend.validar_credencial_azure(azure_request()), False
            )
        elif operation == "replace":
            backend.salvar_credencial_azure_usuario(
                USER_ONE["id"], USER_ONE["email"], backend.validar_credencial_azure(azure_request()), True
            )
        else:
            backend.excluir_credencial_azure_usuario(USER_ONE["id"], USER_ONE["email"])
    assert failed.rolled_back is True
    assert state == original


@pytest.mark.parametrize("field", ["tenant_id", "client_id", "subscription_id"])
def test_invalid_identifiers_are_rejected_without_echo(field):
    values = dict(tenant=TENANT_ONE, client=CLIENT_ONE, secret=SECRET_ONE, subscription=SUBSCRIPTION_ONE)
    key = {"tenant_id": "tenant", "client_id": "client", "subscription_id": "subscription"}[field]
    values[key] = "sensitive-invalid-identifier"
    with pytest.raises(HTTPException) as error:
        backend.validar_credencial_azure(azure_request(**values))
    assert error.value.status_code == 400
    assert "sensitive-invalid-identifier" not in error.value.detail


def test_missing_oversized_and_validation_errors_never_echo_secret():
    with pytest.raises(HTTPException) as missing:
        backend.validar_credencial_azure(backend.CredencialAzure())
    assert missing.value.status_code == 400
    secret = "sensitive-marker-" + ("x" * 4096)
    with pytest.raises(HTTPException) as oversized:
        backend.validar_credencial_azure(azure_request(secret=secret))
    assert secret not in oversized.value.detail

    request = backend.Request({
        "type": "http", "method": "POST", "scheme": "https", "path": "/credenciais/azure",
        "root_path": "", "query_string": b"", "headers": [], "server": ("test", 443),
    })
    error = RequestValidationError([{
        "type": "model_attributes_type", "loc": ("body",), "msg": "invalid", "input": SECRET_ONE,
    }])
    response = asyncio.run(backend.sanitizar_erro_validacao(request, error))
    assert response.status_code == 422
    assert SECRET_ONE.encode() not in response.body


def test_unexpected_backend_error_returns_sanitized_500(monkeypatch):
    monkeypatch.setattr(
        backend, "listar_credenciais_azure_usuario", lambda _uid: (_ for _ in ()).throw(RuntimeError(SECRET_ONE))
    )
    with pytest.raises(HTTPException) as error:
        backend.listar_credenciais_azure(USER_ONE)
    assert error.value.status_code == 500
    assert SECRET_ONE not in error.value.detail


def test_schema_openapi_and_cloud_management_contract(fake_database, monkeypatch):
    source = Path(backend.__file__).read_text()
    schema_sql = source[source.index("CREATE TABLE IF NOT EXISTS cloud_credentials"):source.index("CREATE TABLE IF NOT EXISTS pix_payment_requests")]
    assert "UNIQUE(user_id, provider)" in schema_sql
    schema = backend.app.openapi()
    for method in ("get", "post", "put", "delete"):
        assert schema["paths"]["/credenciais/azure"][method]["security"] == [{"OAuth2PasswordBearer": []}]
    properties = backend.CredencialAzureResponse.model_json_schema()["properties"]
    assert set(properties) == {
        "id", "provider", "tenant_id_masked", "client_id_masked", "subscription_id_masked", "criado_em"
    }
    monkeypatch.setattr(backend.BlobReader, "authenticate", lambda *_args: pytest.fail("Azure called"))
    backend.cadastrar_credencial_azure(azure_request(), USER_ONE)
    backend.listar_credenciais_azure(USER_ONE)
    backend.excluir_credencial_azure(USER_ONE)


def test_azure_provider_errors_are_sanitized_and_service_principal_does_not_use_fallback(monkeypatch, capsys):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "system-sensitive-connection-string")
    reader = BlobReader()
    assert reader.authenticate({"tenant_id": TENANT_ONE, "client_secret": SECRET_ONE}) is False
    assert "system-sensitive-connection-string" not in capsys.readouterr().out

    class BrokenClient:
        def list_containers(self):
            raise AzureError(SECRET_ONE)

        def get_container_client(self, _name):
            raise AzureError(SECRET_ONE)

    reader.client = BrokenClient()
    assert list(reader.list_resources()) == []
    assert reader.get_metadata("azure://container/blob") == {
        "error": "Não foi possível consultar os metadados no Azure Blob Storage"
    }
    assert SECRET_ONE not in capsys.readouterr().out

import copy
import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pydantic
from fastapi import HTTPException


os.environ.setdefault("NANO_IAAS_SECRET_KEY", "gcp-credentials-test-secret")
os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "gcp-credentials-test-encryption-key")
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


PROJECT_ONE = "project-one-invalid"
CLIENT_EMAIL_ONE = "service-one@project-one.invalid"
PRIVATE_KEY_ONE = "fictitious-private-key-material-one"
PRIVATE_KEY_ID_ONE = "fictitious-key-id-one"
PROJECT_TWO = "project-two-invalid"
CLIENT_EMAIL_TWO = "service-two@project-two.invalid"
PRIVATE_KEY_TWO = "fictitious-private-key-material-two"
PRIVATE_KEY_ID_TWO = "fictitious-key-id-two"
USER_ONE = {"id": 51, "email": "user-one@example.invalid"}
USER_TWO = {"id": 52, "email": "user-two@example.invalid"}


def service_account(
    project_id=PROJECT_ONE,
    client_email=CLIENT_EMAIL_ONE,
    private_key=PRIVATE_KEY_ONE,
    private_key_id=PRIVATE_KEY_ID_ONE,
):
    return {
        "type": "service_account",
        "project_id": project_id,
        "private_key_id": private_key_id,
        "private_key": private_key,
        "client_email": client_email,
    }


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
            require("FROM cloud_credentials", "WHERE user_id = %s AND provider = 'gcp'", "ORDER BY id")
            assert len(params) == 1
            record = state["credentials"].get(params[0])
            self.all = [copy.deepcopy(record)] if record else []
        elif normalized.startswith("SELECT id FROM cloud_credentials"):
            require("WHERE user_id = %s AND provider = 'gcp'", "FOR UPDATE")
            assert len(params) == 1
            record = state["credentials"].get(params[0])
            self.one = {"id": record["id"]} if record else None
        elif normalized.startswith("INSERT INTO cloud_credentials"):
            require(
                "INSERT INTO cloud_credentials (user_id, provider, credencial_cifrada)",
                "VALUES (%s, 'gcp', %s)",
                "RETURNING id, credencial_cifrada, criado_em",
            )
            assert len(params) == 2
            user_id, ciphertext = params
            record = {
                "id": 2000 + user_id,
                "credencial_cifrada": ciphertext,
                "criado_em": datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
            }
            state["credentials"][user_id] = record
            self.one = copy.deepcopy(record)
        elif normalized.startswith("UPDATE cloud_credentials"):
            require(
                "SET credencial_cifrada = %s, criado_em = now()",
                "WHERE user_id = %s AND provider = 'gcp'",
                "RETURNING id, credencial_cifrada, criado_em",
            )
            assert len(params) == 2
            ciphertext, user_id = params
            record = state["credentials"][user_id]
            record["credencial_cifrada"] = ciphertext
            record["criado_em"] = datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc)
            self.one = copy.deepcopy(record)
        elif normalized.startswith("DELETE FROM cloud_credentials"):
            require("WHERE user_id = %s AND provider = 'gcp'")
            assert len(params) == 1
            state["credentials"].pop(params[0], None)
        elif normalized.startswith("INSERT INTO audit_log"):
            require(
                "INSERT INTO audit_log (usuario, acao, provider)",
                "VALUES",
                "'gcp'",
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
    backend._fernet = None
    return state, connections


def gcp_request(info=None):
    return backend.CredencialGCP(service_account_json=json.dumps(info or service_account()))


def serialized(value):
    return repr(value)


def decrypted_service_account(ciphertext):
    stored = json.loads(backend.descriptografar(ciphertext))
    return json.loads(stored["service_account_json"])


def test_absence_returns_empty_list_for_authenticated_user(fake_database):
    assert backend.listar_credenciais_gcp(USER_ONE) == []


def test_create_encrypts_full_json_and_returns_only_safe_metadata(fake_database):
    state, connections = fake_database
    response = backend.cadastrar_credencial_gcp(gcp_request(), USER_ONE)

    ciphertext = state["credentials"][USER_ONE["id"]]["credencial_cifrada"]
    for sensitive in (CLIENT_EMAIL_ONE, PRIVATE_KEY_ONE, PRIVATE_KEY_ID_ONE):
        assert sensitive not in ciphertext
        assert sensitive not in serialized(response)
    assert decrypted_service_account(ciphertext) == service_account()
    assert response["provider"] == "gcp"
    assert response["project_id"] == PROJECT_ONE
    assert response["client_email_masked"] == "se***@pr***.invalid"
    assert connections[-1].committed is True


def test_list_is_scoped_exclusively_to_token_user(fake_database):
    backend.cadastrar_credencial_gcp(gcp_request(), USER_ONE)
    backend.cadastrar_credencial_gcp(
        gcp_request(service_account(PROJECT_TWO, CLIENT_EMAIL_TWO, PRIVATE_KEY_TWO, PRIVATE_KEY_ID_TWO)),
        USER_TWO,
    )

    first = backend.listar_credenciais_gcp(USER_ONE)
    second = backend.listar_credenciais_gcp(USER_TWO)

    assert len(first) == len(second) == 1
    assert first[0]["project_id"] == PROJECT_ONE
    assert second[0]["project_id"] == PROJECT_TWO
    for sensitive in (CLIENT_EMAIL_TWO, PRIVATE_KEY_TWO, PRIVATE_KEY_ID_TWO):
        assert sensitive not in serialized(first)


def test_duplicate_create_requires_explicit_replace(fake_database):
    backend.cadastrar_credencial_gcp(gcp_request(), USER_ONE)

    with pytest.raises(HTTPException) as error:
        backend.cadastrar_credencial_gcp(
            gcp_request(service_account(PROJECT_TWO, CLIENT_EMAIL_TWO, PRIVATE_KEY_TWO, PRIVATE_KEY_ID_TWO)),
            USER_ONE,
        )

    assert error.value.status_code == 409
    assert backend.listar_credenciais_gcp(USER_ONE)[0]["project_id"] == PROJECT_ONE


def test_replace_is_transactional_and_does_not_change_other_user(fake_database):
    backend.cadastrar_credencial_gcp(gcp_request(), USER_ONE)
    backend.cadastrar_credencial_gcp(
        gcp_request(service_account(PROJECT_TWO, CLIENT_EMAIL_TWO, PRIVATE_KEY_TWO, PRIVATE_KEY_ID_TWO)),
        USER_TWO,
    )

    replacement = service_account(
        "replacement-project-invalid",
        "replacement-service@replacement.invalid",
        "fictitious-replacement-private-key",
        "fictitious-replacement-key-id",
    )
    response = backend.substituir_credencial_gcp(gcp_request(replacement), USER_ONE)

    assert response["project_id"] == "replacement-project-invalid"
    assert backend.listar_credenciais_gcp(USER_TWO)[0]["project_id"] == PROJECT_TWO


def test_replace_missing_credential_returns_404(fake_database):
    with pytest.raises(HTTPException) as error:
        backend.substituir_credencial_gcp(gcp_request(), USER_ONE)
    assert error.value.status_code == 404


def test_delete_only_removes_authenticated_users_credential(fake_database):
    backend.cadastrar_credencial_gcp(gcp_request(), USER_ONE)
    backend.cadastrar_credencial_gcp(
        gcp_request(service_account(PROJECT_TWO, CLIENT_EMAIL_TWO, PRIVATE_KEY_TWO, PRIVATE_KEY_ID_TWO)),
        USER_TWO,
    )

    response = backend.excluir_credencial_gcp(USER_ONE)

    assert response["ok"] is True
    assert backend.listar_credenciais_gcp(USER_ONE) == []
    assert len(backend.listar_credenciais_gcp(USER_TWO)) == 1


def test_delete_missing_credential_returns_404(fake_database):
    with pytest.raises(HTTPException) as error:
        backend.excluir_credencial_gcp(USER_ONE)
    assert error.value.status_code == 404


def test_audit_contains_only_action_user_and_provider(fake_database):
    state, _ = fake_database
    backend.cadastrar_credencial_gcp(gcp_request(), USER_ONE)
    backend.substituir_credencial_gcp(
        gcp_request(service_account(PROJECT_TWO, CLIENT_EMAIL_TWO, PRIVATE_KEY_TWO, PRIVATE_KEY_ID_TWO)),
        USER_ONE,
    )
    backend.excluir_credencial_gcp(USER_ONE)

    audit = serialized(state["audits"])
    assert USER_ONE["email"] in audit
    assert "CREDENCIAL_CADASTRADA" in audit
    assert "CREDENCIAL_SUBSTITUIDA" in audit
    assert "CREDENCIAL_EXCLUIDA" in audit
    assert "INSERT INTO audit_log (usuario, acao, provider)" in audit
    assert "'gcp'" in audit
    for sensitive in (
        PROJECT_ONE,
        CLIENT_EMAIL_ONE,
        PRIVATE_KEY_ONE,
        PRIVATE_KEY_ID_ONE,
        PROJECT_TWO,
        CLIENT_EMAIL_TWO,
        PRIVATE_KEY_TWO,
        PRIVATE_KEY_ID_TWO,
    ):
        assert sensitive not in audit


@pytest.mark.parametrize("operation", ["create", "replace", "delete"])
def test_audit_failure_rolls_back_mutation(monkeypatch, operation):
    state = {"credentials": {}, "audits": []}
    monkeypatch.setattr(backend, "conectar_db", lambda: FakeConnection(state))
    if operation != "create":
        backend.cadastrar_credencial_gcp(gcp_request(), USER_ONE)
    original = copy.deepcopy(state)

    failed_connection = FakeConnection(state, fail_audit=True)
    monkeypatch.setattr(backend, "conectar_db", lambda: failed_connection)
    with pytest.raises(RuntimeError, match="simulated audit failure"):
        if operation == "create":
            backend.cadastrar_credencial_gcp(gcp_request(), USER_ONE)
        elif operation == "replace":
            backend.substituir_credencial_gcp(
                gcp_request(service_account(PROJECT_TWO, CLIENT_EMAIL_TWO, PRIVATE_KEY_TWO, PRIVATE_KEY_ID_TWO)),
                USER_ONE,
            )
        else:
            backend.excluir_credencial_gcp(USER_ONE)

    assert failed_connection.rolled_back is True
    assert state == original


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        (None, "JSON da credencial GCP inválido"),
        ("not-json-sensitive-marker", "JSON da credencial GCP inválido"),
        ([], "JSON da credencial GCP inválido"),
        ({"private_key": "sensitive-marker"}, "JSON da credencial GCP inválido"),
        (json.dumps([]), "JSON da credencial GCP inválido"),
        (json.dumps({}), "Credencial GCP deve ser do tipo service_account"),
        (json.dumps({"type": "user"}), "Credencial GCP deve ser do tipo service_account"),
        (
            json.dumps({"type": "service_account", "client_email": CLIENT_EMAIL_ONE, "private_key": PRIVATE_KEY_ONE}),
            "Credencial GCP sem o campo obrigatório project_id",
        ),
        (
            json.dumps({"type": "service_account", "project_id": PROJECT_ONE, "private_key": PRIVATE_KEY_ONE}),
            "Credencial GCP sem o campo obrigatório client_email",
        ),
        (
            json.dumps({"type": "service_account", "project_id": PROJECT_ONE, "client_email": CLIENT_EMAIL_ONE}),
            "Credencial GCP sem o campo obrigatório private_key",
        ),
    ],
)
def test_invalid_json_and_missing_fields_never_echo_input(payload, detail):
    with pytest.raises(HTTPException) as error:
        backend.validar_credencial_gcp(backend.CredencialGCP(service_account_json=payload))
    assert error.value.status_code == 400
    assert error.value.detail == detail
    assert "sensitive-marker" not in error.value.detail
    assert CLIENT_EMAIL_ONE not in error.value.detail
    assert PRIVATE_KEY_ONE not in error.value.detail


def test_missing_wrapper_field_is_handled_without_pydantic_echo():
    with pytest.raises(HTTPException) as error:
        backend.validar_credencial_gcp(backend.CredencialGCP())
    assert error.value.status_code == 400
    assert error.value.detail == "JSON da credencial GCP inválido"


def test_schema_and_sql_contract_support_gcp_without_migration():
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


def test_credential_management_never_calls_google_cloud(monkeypatch, fake_database):
    monkeypatch.setattr(
        backend.GCSReader,
        "authenticate",
        lambda *_args, **_kwargs: pytest.fail("credential management called Google Cloud"),
    )
    backend.cadastrar_credencial_gcp(gcp_request(), USER_ONE)
    backend.listar_credenciais_gcp(USER_ONE)
    backend.substituir_credencial_gcp(gcp_request(), USER_ONE)
    backend.excluir_credencial_gcp(USER_ONE)


def test_gcp_authentication_error_does_not_log_credential(monkeypatch, capsys):
    def fail_credentials(_info):
        raise RuntimeError(f"{CLIENT_EMAIL_ONE} {PRIVATE_KEY_ONE} {PRIVATE_KEY_ID_ONE}")

    monkeypatch.setattr(
        "providers.gcp.gcs_reader.service_account.Credentials.from_service_account_info",
        fail_credentials,
    )
    reader = backend.GCSReader()

    assert reader.authenticate({"service_account_json": json.dumps(service_account())}) is False
    output = capsys.readouterr().out
    assert "Erro ao autenticar no GCP" in output
    for sensitive in (CLIENT_EMAIL_ONE, PRIVATE_KEY_ONE, PRIVATE_KEY_ID_ONE):
        assert sensitive not in output


def test_all_gcp_credential_routes_require_bearer_authentication():
    schema = backend.app.openapi()
    for method in ("get", "post", "put", "delete"):
        operation = schema["paths"]["/credenciais/gcp"][method]
        assert operation["security"] == [{"OAuth2PasswordBearer": []}]


def test_openapi_response_schema_has_no_sensitive_gcp_fields():
    properties = backend.CredencialGCPResponse.model_json_schema()["properties"]
    assert set(properties) == {"id", "provider", "project_id", "client_email_masked", "criado_em"}
    assert "private_key" not in serialized(properties)
    assert "private_key_id" not in serialized(properties)
    assert "service_account_json" not in serialized(properties)

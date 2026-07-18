import asyncio
import copy
import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pydantic
import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError


os.environ.setdefault("NANO_IAAS_SECRET_KEY", "self-plan-test-secret")
os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "self-plan-test-encryption-key")
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


USER_ONE = {"id": 81, "full_name": "User One", "email": "one@example.invalid", "plano": "premium", "is_admin": False}
USER_TWO = {"id": 82, "full_name": "User Two", "email": "two@example.invalid", "plano": "popular", "is_admin": False}
ADMIN = {"id": 1, "full_name": "Admin", "email": "admin@example.invalid", "plano": "premium", "is_admin": True}
PAYMENT_PROOF = "fictitious-payment-proof-marker"


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

        if sql.startswith("SELECT id, email, plano, is_admin FROM users"):
            assert "WHERE id = %s FOR UPDATE" in sql
            self.one = copy.deepcopy(state["users"].get(params[0]))
        elif sql.startswith("SELECT id, email, plano FROM users"):
            assert "WHERE id = %s FOR UPDATE" in sql
            user = state["users"].get(params[0])
            self.one = copy.deepcopy(user) if user else None
        elif sql.startswith("UPDATE users SET plano"):
            assert "WHERE id = %s RETURNING id, email, plano, is_admin" in sql
            plano, user_id = params
            state["users"][user_id]["plano"] = plano
            self.one = copy.deepcopy(state["users"][user_id])
        elif sql.startswith("SELECT id, plano FROM pix_payment_requests"):
            assert "WHERE user_id = %s AND status = 'pendente'" in sql
            assert "FOR UPDATE" in sql
            pending = next(
                (item for item in state["pix"].values() if item["user_id"] == params[0] and item["status"] == "pendente"),
                None,
            )
            self.one = {"id": pending["id"], "plano": pending["plano"]} if pending else None
        elif sql.startswith("INSERT INTO pix_payment_requests"):
            assert "INSERT INTO pix_payment_requests (user_id, email, plano, valor_centavos, comprovante)" in sql
            user_id, email, plano, value, proof = params
            pix_id = max(state["pix"], default=9000) + 1
            record = {
                "id": pix_id,
                "user_id": user_id,
                "email": email,
                "plano": plano,
                "valor_centavos": value,
                "comprovante": proof,
                "status": "pendente",
                "criado_em": datetime(2026, 7, 18, 18, 0, tzinfo=timezone.utc),
            }
            state["pix"][pix_id] = record
            self.one = copy.deepcopy(record)
        elif sql.startswith("SELECT user_id FROM pix_payment_requests"):
            assert "WHERE id = %s AND status = 'pendente'" in sql
            assert "FOR UPDATE" not in sql
            record = state["pix"].get(params[0])
            self.one = {"user_id": record["user_id"]} if record and record["status"] == "pendente" else None
        elif sql.startswith("SELECT id, user_id, email, plano, valor_centavos, status FROM pix_payment_requests"):
            assert "WHERE id = %s AND status = 'pendente' FOR UPDATE" in sql
            record = state["pix"].get(params[0])
            self.one = copy.deepcopy(record) if record and record["status"] == "pendente" else None
        elif sql.startswith("UPDATE pix_payment_requests"):
            assert "WHERE id = %s AND status = 'pendente'" in sql
            record = state["pix"].get(params[0])
            if record and record["status"] == "pendente":
                record["status"] = "aprovado"
                record["aprovado_em"] = datetime(2026, 7, 18, 18, 5, tzinfo=timezone.utc)
                self.one = copy.deepcopy(record)
        elif sql.startswith("INSERT INTO audit_log"):
            assert "INSERT INTO audit_log (usuario, acao, provider, recurso, detalhes)" in sql
            if self.connection.fail_audit:
                raise RuntimeError("simulated audit failure with sensitive-marker")
            state["audits"].append({"query": sql, "params": tuple(params)})
        elif sql.startswith("SELECT provider FROM cloud_credentials"):
            assert "WHERE user_id = %s" in sql
            self.all = [(provider,) for provider in state["cloud_credentials"].get(params[0], [])]
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
    state = {
        "users": {81: copy.deepcopy(USER_ONE), 82: copy.deepcopy(USER_TWO), 1: copy.deepcopy(ADMIN)},
        "pix": {},
        "audits": [],
        "cloud_credentials": {81: ["aws", "gcp", "azure"], 82: ["aws"]},
    }
    connections = []

    def connect():
        connection = FakeConnection(state)
        connections.append(connection)
        return connection

    monkeypatch.setattr(backend, "conectar_db", connect)
    return state, connections


def test_user_updates_only_own_plan_and_cloud_credentials_are_untouched(fake_database):
    state, connections = fake_database
    cloud_before = copy.deepcopy(state["cloud_credentials"])
    response = backend.atualizar_meu_plano(backend.PlanoRequest(plano="gratuito"), USER_ONE)
    assert response == {
        "plano_anterior": "premium",
        "plano": "gratuito",
        "alterado": True,
        "message": "Plano atualizado com sucesso.",
    }
    assert state["users"][81]["plano"] == "gratuito"
    assert state["users"][82]["plano"] == "popular"
    assert state["users"][81]["is_admin"] is False
    assert state["cloud_credentials"] == cloud_before
    assert connections[-1].committed is True


@pytest.mark.parametrize("extra", [{"user_id": 82}, {"email": USER_TWO["email"]}, {"is_admin": True}])
def test_request_rejects_attempts_to_change_user_or_admin(extra):
    with pytest.raises(ValidationError):
        backend.PlanoRequest.model_validate({"plano": "gratuito", **extra})


def test_pix_request_rejects_client_defined_price_and_identity():
    with pytest.raises(ValidationError):
        backend.PixRequest.model_validate({
            "plano": "popular",
            "comprovante": PAYMENT_PROOF,
            "valor": 1,
            "user_id": USER_TWO["id"],
        })


def test_invalid_and_paid_direct_updates_are_rejected(fake_database):
    state, _ = fake_database
    before = copy.deepcopy(state)
    with pytest.raises(HTTPException) as invalid:
        backend.atualizar_meu_plano(backend.PlanoRequest(plano="enterprise"), USER_ONE)
    assert invalid.value.status_code == 400
    with pytest.raises(HTTPException) as paid:
        backend.atualizar_meu_plano(backend.PlanoRequest(plano="premium"), USER_TWO)
    assert paid.value.status_code == 403
    assert state == before


def test_same_plan_is_idempotent_and_audited(fake_database):
    state, _ = fake_database
    response = backend.atualizar_meu_plano(backend.PlanoRequest(plano="popular"), USER_TWO)
    assert response["alterado"] is False
    assert response["plano_anterior"] == response["plano"] == "popular"
    audit = repr(state["audits"])
    assert "PLANO_MANTIDO" in audit
    assert "plano_anterior=popular;plano_novo=popular" in audit


def test_audit_failure_rolls_back_plan_update(monkeypatch, fake_database):
    state, _ = fake_database
    original = copy.deepcopy(state)
    failed = FakeConnection(state, fail_audit=True)
    monkeypatch.setattr(backend, "conectar_db", lambda: failed)
    with pytest.raises(HTTPException) as error:
        backend.atualizar_meu_plano(backend.PlanoRequest(plano="gratuito"), USER_ONE)
    assert error.value.status_code == 500
    assert "sensitive-marker" not in error.value.detail
    assert failed.rolled_back is True
    assert state == original


def test_audit_records_actor_action_old_new_and_no_sensitive_data(fake_database):
    state, _ = fake_database
    backend.atualizar_meu_plano(backend.PlanoRequest(plano="gratuito"), USER_ONE)
    audit = repr(state["audits"])
    assert USER_ONE["email"] in audit
    assert "PLANO_ATUALIZADO" in audit
    assert "plano_anterior=premium;plano_novo=gratuito" in audit
    for forbidden in ("token", "comprovante", PAYMENT_PROOF, "is_admin"):
        assert forbidden not in audit


def test_paid_plan_requires_pending_pix_then_admin_approval(fake_database):
    state, _ = fake_database
    state["users"][81]["plano"] = "gratuito"
    user = {**USER_ONE, "plano": "gratuito"}
    request = backend.solicitar_ativacao_pix(
        backend.PixRequest(plano="premium", comprovante=PAYMENT_PROOF), user
    )
    assert request["status"] == "pendente"
    assert state["users"][81]["plano"] == "gratuito"
    assert PAYMENT_PROOF not in repr(state["audits"])

    with pytest.raises(HTTPException) as duplicate:
        backend.solicitar_ativacao_pix(
            backend.PixRequest(plano="premium", comprovante="another-proof"), user
        )
    assert duplicate.value.status_code == 409

    result = backend.admin_aprovar_pix(request["id"], ADMIN)
    assert result["usuario"]["plano"] == "premium"
    assert state["users"][81]["plano"] == "premium"
    assert "PIX_APROVADO" in repr(state["audits"])
    assert "usuario_id=81;plano_anterior=gratuito;plano_novo=premium" in repr(state["audits"])

    with pytest.raises(HTTPException) as reused:
        backend.admin_aprovar_pix(request["id"], ADMIN)
    assert reused.value.status_code == 404


def test_common_user_cannot_approve_or_reuse_rejected_request(fake_database):
    state, _ = fake_database
    state["users"][81]["plano"] = "gratuito"
    request = backend.solicitar_ativacao_pix(
        backend.PixRequest(plano="popular", comprovante=PAYMENT_PROOF),
        {**USER_ONE, "plano": "gratuito"},
    )
    with pytest.raises(HTTPException) as forbidden:
        backend.admin_aprovar_pix(request["id"], USER_ONE)
    assert forbidden.value.status_code == 403
    assert state["users"][81]["plano"] == "gratuito"

    state["pix"][request["id"]]["status"] = "rejeitado"
    with pytest.raises(HTTPException) as rejected:
        backend.admin_aprovar_pix(request["id"], ADMIN)
    assert rejected.value.status_code == 404
    assert state["users"][81]["plano"] == "gratuito"


def test_pix_audit_failure_rolls_back_request(monkeypatch, fake_database):
    state, _ = fake_database
    state["users"][81]["plano"] = "gratuito"
    original = copy.deepcopy(state)
    failed = FakeConnection(state, fail_audit=True)
    monkeypatch.setattr(backend, "conectar_db", lambda: failed)
    with pytest.raises(HTTPException) as error:
        backend.solicitar_ativacao_pix(
            backend.PixRequest(plano="popular", comprovante=PAYMENT_PROOF),
            {**USER_ONE, "plano": "gratuito"},
        )
    assert error.value.status_code == 500
    assert failed.rolled_back is True
    assert state == original


def test_approval_audit_failure_rolls_back_paid_activation(monkeypatch, fake_database):
    state, _ = fake_database
    state["users"][81]["plano"] = "gratuito"
    request = backend.solicitar_ativacao_pix(
        backend.PixRequest(plano="popular", comprovante=PAYMENT_PROOF),
        {**USER_ONE, "plano": "gratuito"},
    )
    original = copy.deepcopy(state)
    failed = FakeConnection(state, fail_audit=True)
    monkeypatch.setattr(backend, "conectar_db", lambda: failed)
    with pytest.raises(HTTPException) as error:
        backend.admin_aprovar_pix(request["id"], ADMIN)
    assert error.value.status_code == 500
    assert "sensitive-marker" not in error.value.detail
    assert failed.rolled_back is True
    assert state == original


def test_get_me_reflects_updated_plan(fake_database):
    state, _ = fake_database
    backend.atualizar_meu_plano(backend.PlanoRequest(plano="gratuito"), USER_ONE)
    current = {**USER_ONE, "plano": state["users"][81]["plano"]}
    response = backend.meus_dados(current)
    assert response["plano"] == "gratuito"
    assert response["providers_configurados"] == ["aws", "gcp", "azure"]


def test_server_is_authoritative_for_options_and_prices():
    response = backend.opcoes_atualizacao_plano(USER_ONE)
    assert response["plano_atual"] == "premium"
    assert [item["plano"] for item in response["opcoes"]] == list(backend.PLANOS_VALIDOS)
    assert {item["plano"]: item["valor"] for item in response["opcoes"]} == backend.PLANOS_VALORES
    assert response["opcoes"][0]["modo_ativacao"] == "direta"
    assert all(item["modo_ativacao"] == "pix_aprovacao_manual" for item in response["opcoes"][1:])


def test_422_handler_sanitizes_extra_fields_and_payment_input():
    request = backend.Request({
        "type": "http", "method": "PATCH", "scheme": "https", "path": "/me/plano",
        "root_path": "", "query_string": b"", "headers": [], "server": ("test", 443),
    })
    error = RequestValidationError([{
        "type": "extra_forbidden", "loc": ("body", "is_admin"), "msg": "Extra inputs are not permitted",
        "input": PAYMENT_PROOF,
    }])
    response = asyncio.run(backend.sanitizar_erro_validacao(request, error))
    assert response.status_code == 422
    assert PAYMENT_PROOF.encode() not in response.body
    assert json.loads(response.body) == {"detail": "Requisição de atualização de plano inválida"}


def test_schema_and_routes_match_real_contract():
    source = Path(backend.__file__).read_text()
    users_schema = source[source.index("CREATE TABLE IF NOT EXISTS users"):source.index("CREATE TABLE IF NOT EXISTS cloud_credentials")]
    pix_schema = source[source.index("CREATE TABLE IF NOT EXISTS pix_payment_requests"):source.index("CREATE TABLE IF NOT EXISTS login_attempts")]
    assert "plano TEXT NOT NULL DEFAULT 'gratuito'" in users_schema
    assert "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE" in pix_schema
    assert "status TEXT NOT NULL DEFAULT 'pendente'" in pix_schema
    schema = backend.app.openapi()
    assert schema["paths"]["/me/plano"]["patch"]["security"] == [{"OAuth2PasswordBearer": []}]
    assert schema["paths"]["/me/plano/opcoes"]["get"]["security"] == [{"OAuth2PasswordBearer": []}]
    assert schema["paths"]["/pix/solicitacao"]["post"]["security"] == [{"OAuth2PasswordBearer": []}]

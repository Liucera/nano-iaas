import asyncio
import json
import os
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest
import pydantic
from fastapi import HTTPException
from starlette.requests import Request


os.environ.setdefault("NANO_IAAS_SECRET_KEY", "local-test-secret")
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

os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "local-test-encryption-key")

from web.backend import main as backend


CURRENT_PASSWORD = "LocalCurrent-123"
NEW_PASSWORD = "LocalNew-456"
USER = {"id": 77, "email": "local-user@example.invalid"}
FRONTEND = Path(__file__).parents[1] / "docs" / "index.html"


def change_request(**changes):
    data = {
        "senha_atual": CURRENT_PASSWORD,
        "nova_senha": NEW_PASSWORD,
        "confirmacao_nova_senha": NEW_PASSWORD,
    }
    data.update(changes)
    return backend.ChangePasswordRequest(**data)


@pytest.fixture
def isolated_change(monkeypatch):
    captured = {}
    old_hash = backend.gerar_hash_senha(CURRENT_PASSWORD)
    monkeypatch.setattr(
        backend,
        "buscar_senha_hash_usuario",
        lambda user_id: {"id": user_id, "senha_hash": old_hash},
    )

    def update(user_id, new_hash, user_email):
        captured["update"] = (user_id, new_hash)
        captured["audit"] = (user_email, "SENHA", "-", "-", "senha alterada")
        return True

    monkeypatch.setattr(backend, "atualizar_senha_usuario", update)
    captured["old_hash"] = old_hash
    return captured


def assert_change_error(request, status_code, detail):
    with pytest.raises(HTTPException) as error:
        backend.alterar_minha_senha(request, USER)
    assert error.value.status_code == status_code
    assert error.value.detail == detail


def test_change_password_with_correct_current_password(isolated_change):
    response = backend.alterar_minha_senha(change_request(), USER)

    assert response == {"ok": True, "message": "Senha alterada com sucesso."}
    user_id, new_hash = isolated_change["update"]
    assert user_id == USER["id"]
    assert new_hash != isolated_change["old_hash"]
    assert backend.verificar_senha(NEW_PASSWORD, new_hash)
    assert not backend.verificar_senha(CURRENT_PASSWORD, new_hash)


def test_wrong_current_password_does_not_update(isolated_change):
    assert_change_error(
        change_request(senha_atual="DifferentCurrent-789"),
        401,
        "Senha atual incorreta",
    )
    assert "update" not in isolated_change


def test_new_password_confirmation_mismatch_does_not_update(isolated_change):
    assert_change_error(
        change_request(confirmacao_nova_senha="DifferentConfirm-789"),
        400,
        "A confirmação da nova senha não confere",
    )
    assert "update" not in isolated_change


def test_new_password_below_minimum_does_not_update(isolated_change):
    assert_change_error(
        change_request(nova_senha="short", confirmacao_nova_senha="short"),
        400,
        "A nova senha deve ter pelo menos 8 caracteres",
    )
    assert "update" not in isolated_change


def test_new_password_equal_to_current_does_not_update(isolated_change):
    assert_change_error(
        change_request(
            nova_senha=CURRENT_PASSWORD,
            confirmacao_nova_senha=CURRENT_PASSWORD,
        ),
        400,
        "A nova senha deve ser diferente da senha atual",
    )
    assert "update" not in isolated_change


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"senha_atual": ""}, "Informe a senha atual"),
        ({"nova_senha": ""}, "Informe a nova senha"),
        ({"confirmacao_nova_senha": ""}, "Confirme a nova senha"),
    ],
)
def test_required_password_fields(changes, detail, isolated_change):
    assert_change_error(change_request(**changes), 400, detail)
    assert "update" not in isolated_change


def test_change_is_limited_to_authenticated_user(isolated_change):
    backend.alterar_minha_senha(change_request(), USER)
    assert isolated_change["update"][0] == USER["id"]


def test_response_and_audit_do_not_contain_password_or_hash(isolated_change):
    response = backend.alterar_minha_senha(change_request(), USER)
    serialized = repr(response)
    audit = repr(isolated_change["audit"])

    for sensitive in (
        CURRENT_PASSWORD,
        NEW_PASSWORD,
        isolated_change["old_hash"],
        isolated_change["update"][1],
    ):
        assert sensitive not in serialized
        assert sensitive not in audit
    assert isolated_change["audit"][-1] == "senha alterada"


def test_missing_authenticated_user_does_not_update(monkeypatch):
    updated = []
    monkeypatch.setattr(backend, "buscar_senha_hash_usuario", lambda _user_id: None)
    monkeypatch.setattr(
        backend,
        "atualizar_senha_usuario",
        lambda *args: updated.append(args),
    )
    assert_change_error(change_request(), 401, "Token inválido")
    assert updated == []


def test_unauthenticated_request_is_rejected():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/me/change-password",
            "headers": [],
        }
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(backend.oauth2_scheme(request))
    assert error.value.status_code == 401
    assert "senha" not in str(error.value.detail).lower()


def test_invalid_token_is_rejected():
    with pytest.raises(HTTPException) as error:
        backend.usuario_atual("invalid-local-token")
    assert error.value.status_code == 401
    for sensitive in (CURRENT_PASSWORD, NEW_PASSWORD):
        assert sensitive not in str(error.value.detail)


class UpdateCursor:
    def __init__(self, result=(77,)):
        self.result = result
        self.query = ""
        self.params = ()
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.query = " ".join(query.split())
        self.params = params
        self.executions.append((self.query, params))

    def fetchone(self):
        return self.result


class UpdateConnection:
    def __init__(self, result=(77,)):
        self.cursor_instance = UpdateCursor(result)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_persistence_updates_only_password_hash_for_user_and_commits(monkeypatch):
    connection = UpdateConnection()
    monkeypatch.setattr(backend, "conectar_db", lambda: connection)

    assert backend.atualizar_senha_usuario(77, "local-bcrypt-hash", USER["email"])
    cursor = connection.cursor_instance
    update_query, update_params = cursor.executions[0]
    assert update_query == (
        "UPDATE users SET senha_hash = %s WHERE id = %s RETURNING id"
    )
    assert update_params == ("local-bcrypt-hash", 77)
    audit_query, audit_params = cursor.executions[1]
    assert "INSERT INTO audit_log" in audit_query
    assert audit_params == (USER["email"], "SENHA", "-", "-", "senha alterada")
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_persistence_does_not_commit_when_user_is_missing(monkeypatch):
    connection = UpdateConnection(result=None)
    monkeypatch.setattr(backend, "conectar_db", lambda: connection)

    assert backend.atualizar_senha_usuario(77, "local-bcrypt-hash", USER["email"]) is False
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed

def test_audit_failure_rolls_back_password_update(monkeypatch):
    class FailingAuditCursor(UpdateCursor):
        def execute(self, query, params):
            super().execute(query, params)
            if "INSERT INTO audit_log" in self.query:
                raise RuntimeError("simulated audit failure")

    connection = UpdateConnection()
    connection.cursor_instance = FailingAuditCursor()
    monkeypatch.setattr(backend, "conectar_db", lambda: connection)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        backend.atualizar_senha_usuario(
            77,
            "local-bcrypt-hash",
            USER["email"],
        )
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed



def test_openapi_contract_is_authenticated_and_has_no_client_user_id():
    operation = backend.app.openapi()["paths"]["/me/change-password"]["post"]
    request_schema = backend.app.openapi()["components"]["schemas"][
        "ChangePasswordRequest"
    ]
    response_schema = backend.app.openapi()["components"]["schemas"][
        "ChangePasswordResponse"
    ]

    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert set(request_schema["required"]) == {
        "senha_atual",
        "nova_senha",
        "confirmacao_nova_senha",
    }
    assert "user_id" not in request_schema["properties"]
    assert set(response_schema["properties"]) == {"ok", "message"}


def frontend_source():
    return FRONTEND.read_text(encoding="utf-8")


def function_body(source, name):
    match = re.search(rf"(?:async )?function {name}\([^)]*\) \{{", source)
    assert match, f"função {name} não encontrada"
    start = match.end()
    depth = 1
    quote = None
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ('"', "'", "`"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index]
    raise AssertionError(f"fim da função {name} não encontrado")


def test_frontend_has_authenticated_change_password_option_and_form():
    source = frontend_source()
    form = function_body(source, "exibirFormularioAlterarSenha")

    assert "Alterar senha" in source
    assert '<form id="change-password-form"' in form
    assert form.count('type="password"') == 3
    assert 'autocomplete="current-password"' in form
    assert form.count('autocomplete="new-password"') == 2
    assert form.count(" required") == 3
    assert 'type="submit"' in form
    assert 'addEventListener("submit", alterarSenha)' in form


def test_frontend_validates_and_sends_only_expected_payload():
    body = function_body(frontend_source(), "alterarSenha")

    assert "event.preventDefault()" in body
    assert "envioAlteracaoSenhaEmAndamento" in body
    assert "novaSenha.length < 8" in body
    assert "novaSenha !== confirmacao" in body
    assert "novaSenha === senhaAtual" in body
    assert 'apiFetch("/me/change-password"' in body
    assert "senha_atual: senhaAtual" in body
    assert "nova_senha: novaSenha" in body
    assert "confirmacao_nova_senha: confirmacao" in body
    assert "user_id" not in body


def test_frontend_clears_fields_and_reports_success_without_persisting_passwords():
    source = frontend_source()
    body = function_body(source, "alterarSenha")

    assert "form.reset()" in body
    assert "Senha alterada com sucesso." in body
    assert "botao.disabled = true" in body
    assert "botao.disabled = false" in body
    assert "console." not in body
    assert "localStorage" not in body
    assert "sessionStorage" not in body


def test_wrong_current_password_is_sanitized_without_ending_valid_session():
    api_fetch = function_body(frontend_source(), "apiFetch")
    change = function_body(frontend_source(), "alterarSenha")

    assert "preserveSessionOn401 = false" in api_fetch
    assert 'data.detail === "Senha atual incorreta"' in api_fetch
    assert "res.status === 401 && !preservarSessao" in api_fetch
    assert "preserveSessionOn401: true" in change
    assert "e.message" in change

def test_frontend_change_password_behavior_with_mocked_api():
    source = frontend_source()
    functions = (
        "async function apiFetch(path, options = {}) {"
        + function_body(source, "apiFetch")
        + "}\nasync function alterarSenha(event) {"
        + function_body(source, "alterarSenha")
        + "}"
    )
    harness = r"""
const functionsSource = process.argv[1];
const API = "https://api.invalid";
let token = "local-token";
let envioAlteracaoSenhaEmAndamento = false;
let sessionExpired = 0;
let fetchCalls = [];
let responseStatus = 200;
let responseBody = { ok: true, message: "Senha alterada com sucesso." };
let releaseFetch = null;
let holdFetch = false;

function sessaoExpirada() { sessionExpired += 1; }
const message = { textContent: "", className: "" };
const button = { disabled: false };
global.document = {
  getElementById(id) {
    if (id === "change-password-message") return message;
    if (id === "change-password-submit") return button;
    throw new Error("unexpected element: " + id);
  },
};
global.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  if (holdFetch) await new Promise(resolve => { releaseFetch = resolve; });
  return {
    status: responseStatus,
    ok: responseStatus >= 200 && responseStatus < 300,
    async json() { return responseBody; },
  };
};
eval(functionsSource);

function makeEvent(current, next, confirmation) {
  const form = {
    elements: {
      senha_atual: { value: current },
      nova_senha: { value: next },
      confirmacao_nova_senha: { value: confirmation },
    },
    resets: 0,
    reset() { this.resets += 1; },
  };
  return { currentTarget: form, preventDefault() {}, form };
}

(async () => {
  const localCases = [
    ["", "NextLocal-456", "NextLocal-456", "Preencha os três campos"],
    ["CurrentLocal-123", "short", "short", "pelo menos 8"],
    ["CurrentLocal-123", "NextLocal-456", "OtherLocal-789", "não confere"],
    ["CurrentLocal-123", "CurrentLocal-123", "CurrentLocal-123", "diferente"],
  ];
  for (const testCase of localCases) {
    const before = fetchCalls.length;
    const event = makeEvent(testCase[0], testCase[1], testCase[2]);
    await alterarSenha(event);
    if (fetchCalls.length !== before) throw new Error("local validation called API");
    if (!message.textContent.includes(testCase[3])) throw new Error("wrong local message");
  }

  holdFetch = true;
  const success = makeEvent("CurrentLocal-123", "NextLocal-456", "NextLocal-456");
  const first = alterarSenha(success);
  await new Promise(resolve => setTimeout(resolve, 0));
  const second = alterarSenha(success);
  if (fetchCalls.length !== 1 || !button.disabled) throw new Error("duplicate submit allowed");
  releaseFetch();
  await Promise.all([first, second]);
  if (success.form.resets !== 1) throw new Error("form not reset");
  if (message.textContent !== "Senha alterada com sucesso.") throw new Error("success missing");
  const sent = JSON.parse(fetchCalls[0].options.body);
  const keys = Object.keys(sent).sort().join(",");
  if (keys !== "confirmacao_nova_senha,nova_senha,senha_atual") throw new Error("payload mismatch");
  if (fetchCalls[0].options.headers.Authorization !== "Bearer local-token") throw new Error("auth missing");
  if (button.disabled || envioAlteracaoSenhaEmAndamento) throw new Error("submit remained locked");

  holdFetch = false;
  responseStatus = 401;
  responseBody = { detail: "Senha atual incorreta" };
  const wrong = makeEvent("WrongLocal-123", "NextLocal-456", "NextLocal-456");
  await alterarSenha(wrong);
  if (sessionExpired !== 0) throw new Error("valid session was ended");
  if (message.textContent !== "Senha atual incorreta") throw new Error("backend error not shown");
  if (wrong.form.resets !== 0) throw new Error("failed form was reset");
  responseBody = { detail: "Token inválido" };
  const invalidToken = makeEvent("CurrentLocal-123", "NextLocal-456", "NextLocal-456");
  await alterarSenha(invalidToken);
  if (sessionExpired !== 1) throw new Error("invalid token did not end session");
  if (message.textContent !== "Sessão expirada") throw new Error("invalid token message mismatch");
  if (invalidToken.form.resets !== 0) throw new Error("invalid token form was reset");


  process.stdout.write(JSON.stringify({
    calls: fetchCalls.length,
    sessionExpired,
    successReset: success.form.resets,
    wrongReset: wrong.form.resets,
  }));
})().catch(error => {
  process.stderr.write(error.stack);
  process.exit(1);
});
"""
    completed = subprocess.run(
        ["node", "-e", harness, functions],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result == {
        "calls": 3,
        "sessionExpired": 1,
        "successReset": 1,
        "wrongReset": 0,
    }

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pydantic
import pytest
from fastapi import HTTPException


os.environ.setdefault("NANO_IAAS_SECRET_KEY", "messages-test-secret")
os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "messages-test-encryption-key")

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


ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "docs" / "index.html"
BACKEND = ROOT / "web" / "backend" / "main.py"


@pytest.mark.parametrize("mensagem", sorted(backend.ERROS_OPERACIONAIS_PUBLICOS))
def test_backend_preserva_somente_erros_operacionais_publicos(mensagem):
    with pytest.raises(HTTPException) as erro:
        backend.responder_erro_operacional(ValueError(mensagem))

    assert erro.value.status_code == 400
    assert erro.value.detail == mensagem


def test_backend_nao_reflete_value_error_desconhecido():
    marcador = "segredo-interno-simulado-nao-divulgar"

    with pytest.raises(HTTPException) as erro:
        backend.responder_erro_operacional(ValueError(marcador))

    assert erro.value.status_code == 400
    assert erro.value.detail == "Não foi possível processar a solicitação do provider"
    assert marcador not in erro.value.detail


def test_backend_publico_nao_contem_mensagens_obsoletas():
    source = BACKEND.read_text(encoding="utf-8")
    obsoletas = {
        "Servico de autenticacao temporariamente indisponivel",
        "Nao combine campos dos contratos novo e legado",
        "O nome completo deve ter no maximo 150 caracteres",
        "Plano invalido",
        "Versao dos Termos de Uso invalida",
        "Versao da Política de Privacidade invalida",
        "Versao legada dos Termos de Uso invalida",
        "Solicitacao Pix pendente nao encontrada",
        "Nenhuma credencial AWS cadastrada para este usuario",
        "Nenhuma credencial GCP cadastrada para este usuario",
        "Nenhuma credencial Azure cadastrada para este usuario",
        "Erro interno ao processar a solicitacao",
    }
    assert all(mensagem not in source for mensagem in obsoletas)


def api_fetch_source():
    html = FRONTEND.read_text(encoding="utf-8")
    return html[
        html.index("async function apiFetch(path, options = {})"):
        html.index("const detalhesSemCredencial")
    ]


API_FETCH_HARNESS = r"""
const scenario = JSON.parse(process.argv[1]);
const source = process.argv[2];
const API = "https://api.invalid";
let token = "token-simulado";
let sessionExpired = 0;

function sessaoExpirada() {
  sessionExpired += 1;
}

globalThis.fetch = async () => {
  if (scenario.networkError) throw new Error("network marker");
  return {
    status: scenario.status,
    ok: scenario.status >= 200 && scenario.status < 300,
    headers: {
      get(name) {
        return name === "Retry-After" ? (scenario.retryAfter || null) : null;
      },
    },
    async json() {
      return scenario.body;
    },
  };
};

eval(`${source}
globalThis.apiFetchTest = apiFetch;`);

(async () => {
  try {
    await apiFetchTest("/teste");
    process.stdout.write(JSON.stringify({ ok: true, sessionExpired }));
  } catch (error) {
    process.stdout.write(JSON.stringify({
      ok: false,
      message: error.message,
      status: error.status,
      retryAfter: error.retryAfter ?? null,
      sessionExpired,
    }));
  }
})().catch((error) => {
  process.stderr.write(error.stack || error.message);
  process.exit(1);
});
"""


def executar_api_fetch(cenario):
    resultado = subprocess.run(
        ["node", "-e", API_FETCH_HARNESS, json.dumps(cenario), api_fetch_source()],
        check=False,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


@pytest.mark.frontend_static
@pytest.mark.parametrize(
    ("cenario", "mensagem", "status", "retry_after", "sessao_expirada"),
    [
        (
            {"status": 400, "body": {}},
            "Não foi possível concluir a solicitação.", 400, None, 0,
        ),
        (
            {"status": 403, "body": {}},
            "Você não tem permissão para realizar esta operação.", 403, None, 0,
        ),
        (
            {"status": 404, "body": {}},
            "O recurso solicitado não foi encontrado.", 404, None, 0,
        ),
        (
            {"status": 409, "body": {"detail": "Conflito seguro retornado pela API"}},
            "Conflito seguro retornado pela API", 409, None, 0,
        ),
        (
            {"status": 422, "body": {}},
            "Revise os dados informados e tente novamente.", 422, None, 0,
        ),
        (
            {"status": 429, "body": {}, "retryAfter": "17"},
            "Muitas solicitações. Tente novamente mais tarde.", 429, "17", 0,
        ),
        (
            {"status": 500, "body": {}},
            "Não foi possível processar a solicitação.", 500, None, 0,
        ),
        (
            {"status": 502, "body": {}},
            "Não foi possível consultar o serviço externo.", 502, None, 0,
        ),
        (
            {"status": 401, "body": {"detail": "Token inválido"}},
            "Sessão expirada", 401, None, 1,
        ),
        (
            {"networkError": True},
            "Não foi possível conectar à API.", 0, None, 0,
        ),
    ],
)
def test_api_fetch_preserva_status_retry_after_e_fallback(
    cenario, mensagem, status, retry_after, sessao_expirada
):
    assert executar_api_fetch(cenario) == {
        "ok": False,
        "message": mensagem,
        "status": status,
        "retryAfter": retry_after,
        "sessionExpired": sessao_expirada,
    }


SET_STATUS_HARNESS = r"""
const source = process.argv[1];
const attributes = {};
let focusCalls = 0;
let focusOptions = null;
const element = {
  textContent: "",
  className: "",
  setAttribute(name, value) {
    attributes[name] = value;
  },
  focus(options) {
    focusCalls += 1;
    focusOptions = options;
  },
};

globalThis.document = {
  getElementById(id) {
    if (id !== "status") throw new Error("elemento inesperado");
    return element;
  },
};

eval(`${source}
globalThis.setStatusTest = setStatus;`);

setStatusTest("Falha controlada", "error");
const errorState = {
  text: element.textContent,
  className: element.className,
  role: attributes.role,
  live: attributes["aria-live"],
  atomic: attributes["aria-atomic"],
  focusCalls,
  preventScroll: focusOptions && focusOptions.preventScroll,
};

setStatusTest("Operação concluída", "success");
const successState = {
  text: element.textContent,
  className: element.className,
  role: attributes.role,
  live: attributes["aria-live"],
  atomic: attributes["aria-atomic"],
  focusCalls,
};

process.stdout.write(JSON.stringify({ errorState, successState }));
"""


@pytest.mark.frontend_static
def test_status_real_anuncia_erro_e_move_foco_sem_repetir_no_sucesso():
    html = FRONTEND.read_text(encoding="utf-8")
    source = html[
        html.index("function setStatus(msg, tipo)"):
        html.index("async function apiFetch(path, options = {})")
    ]
    resultado = subprocess.run(
        ["node", "-e", SET_STATUS_HARNESS, source],
        check=False,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    estados = json.loads(resultado.stdout)

    assert estados["errorState"] == {
        "text": "Falha controlada",
        "className": "status error",
        "role": "alert",
        "live": "assertive",
        "atomic": "true",
        "focusCalls": 1,
        "preventScroll": True,
    }
    assert estados["successState"] == {
        "text": "Operação concluída",
        "className": "status success",
        "role": "status",
        "live": "polite",
        "atomic": "true",
        "focusCalls": 1,
    }


@pytest.mark.frontend_static
def test_regioes_de_mensagem_possuem_semantica_acessivel():
    html = FRONTEND.read_text(encoding="utf-8")

    assert (
        'id="status" role="status" aria-live="polite" '
        'aria-atomic="true" tabindex="-1"'
    ) in html
    assert html.count(
        'role="alert" aria-live="polite" aria-atomic="true" tabindex="-1"></div>'
    ) == 5

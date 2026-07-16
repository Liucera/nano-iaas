import os
import re
import sys
import types
from html.parser import HTMLParser
from pathlib import Path

import pytest
import pydantic
from fastapi import HTTPException


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


def cadastro_request(**changes):
    data = {
        "full_name": "  Maria da Silva  ",
        "email": "  MARIA@EXAMPLE.COM  ",
        "senha": "senha-segura",
        "plano": "premium",
        "aceite_termos": True,
        "aceite_privacidade": True,
        "terms_version": "2026-07-15",
        "privacy_version": "2026-07-15",
    }
    data.update(changes)
    return backend.CadastroRequest(**data)


def cadastro_legado_request(**changes):
    data = {
        "email": "  LEGADO@EXAMPLE.COM  ",
        "senha": "senha-segura",
        "plano": "premium",
        "aceite_termos": True,
        "versao_termos": "beta-2026-07",
    }
    data.update(changes)
    return backend.CadastroRequest(**data)


@pytest.fixture
def cadastro_isolado(monkeypatch):
    captured = {}
    monkeypatch.setattr(backend, "buscar_usuario_por_email", lambda email: captured.setdefault("lookup", email) and None)
    monkeypatch.setattr(backend, "gerar_hash_senha", lambda senha: f"hash:{senha}")

    def criar(*args):
        captured["create"] = args
        return {
            "id": 42,
            "full_name": args[0],
            "email": args[1],
            "plano": "gratuito",
            "is_admin": False,
        }

    monkeypatch.setattr(backend, "criar_usuario", criar)
    monkeypatch.setattr(backend, "criar_token", lambda payload: captured.setdefault("token_payload", payload) or "token")
    monkeypatch.setattr(backend, "registrar_acesso", lambda *args: captured.setdefault("audit", args))
    return captured


def assert_http_error(request, detail, status_code=400):
    with pytest.raises(HTTPException) as error:
        backend.cadastro(request)
    assert error.value.status_code == status_code
    assert detail in error.value.detail


def test_cadastro_valido_com_full_name_normalizado(cadastro_isolado):
    response = backend.cadastro(cadastro_request())
    assert response["token_type"] == "bearer"
    assert cadastro_isolado["create"][0] == "Maria da Silva"


def test_cadastro_legado_valido_persiste_campos_compativeis(cadastro_isolado):
    response = backend.cadastro(cadastro_legado_request())
    assert response["token_type"] == "bearer"
    assert cadastro_isolado["create"] == (
        None,
        "legado@example.com",
        "hash:senha-segura",
        True,
        True,
        "beta-2026-07",
        "beta-2026-07",
    )


def test_cadastro_legado_com_aceite_falso_rejeitado(cadastro_isolado):
    assert_http_error(cadastro_legado_request(aceite_termos=False), "Termos de Uso")


def test_cadastro_legado_com_versao_diferente_rejeitado(cadastro_isolado):
    assert_http_error(cadastro_legado_request(versao_termos="outra"), "Versao legada")


@pytest.mark.parametrize(
    "changes",
    [
        {"full_name": "Maria"},
        {"aceite_privacidade": True},
        {"terms_version": "2026-07-15"},
        {"privacy_version": "2026-07-15"},
        {
            "aceite_privacidade": True,
            "terms_version": "2026-07-15",
            "privacy_version": "2026-07-15",
        },
    ],
)
def test_payload_hibrido_incompleto_rejeitado(cadastro_isolado, changes):
    assert_http_error(cadastro_legado_request(**changes), "Contrato de cadastro incompleto")


def test_contrato_novo_nao_aceita_campo_legado(cadastro_isolado):
    assert_http_error(
        cadastro_request(versao_termos="beta-2026-07"),
        "Nao combine",
    )


def test_nome_vazio(cadastro_isolado):
    assert_http_error(cadastro_request(full_name=""), "pelo menos 3")


def test_nome_somente_espacos(cadastro_isolado):
    assert_http_error(cadastro_request(full_name="   "), "pelo menos 3")


def test_nome_abaixo_do_minimo(cadastro_isolado):
    assert_http_error(cadastro_request(full_name="Li"), "pelo menos 3")


def test_nome_acima_do_maximo(cadastro_isolado):
    assert_http_error(cadastro_request(full_name="A" * 151), "150")


def test_email_normalizado_para_lowercase(cadastro_isolado):
    backend.cadastro(cadastro_request())
    assert cadastro_isolado["lookup"] == "maria@example.com"
    assert cadastro_isolado["create"][1] == "maria@example.com"


def test_senha_invalida(cadastro_isolado):
    assert_http_error(cadastro_request(senha="curta"), "8 caracteres")


def test_termos_nao_aceitos(cadastro_isolado):
    assert_http_error(cadastro_request(aceite_termos=False), "Termos de Uso")


def test_privacidade_nao_aceita(cadastro_isolado):
    assert_http_error(cadastro_request(aceite_privacidade=False), "Política de Privacidade")


def test_versao_termos_invalida(cadastro_isolado):
    assert_http_error(cadastro_request(terms_version="antiga"), "Termos de Uso invalida")


def test_versao_privacidade_invalida(cadastro_isolado):
    assert_http_error(cadastro_request(privacy_version="antiga"), "Privacidade invalida")


def test_email_duplicado(cadastro_isolado, monkeypatch):
    monkeypatch.setattr(backend, "buscar_usuario_por_email", lambda email: {"id": 1})
    assert_http_error(cadastro_request(), "Ja existe", 409)


class CaptureCursor:
    def __init__(self):
        self.query = ""
        self.params = ()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, query, params=None):
        self.query = " ".join(query.split())
        self.params = params
    def fetchone(self):
        return {"id": 1, "full_name": "Maria", "email": "maria@example.com", "plano": "gratuito", "is_admin": False}


class CaptureConnection:
    def __init__(self):
        self.cursor_instance = CaptureCursor()
        self.committed = False
        self.closed = False
    def cursor(self, *args, **kwargs):
        return self.cursor_instance
    def commit(self):
        self.committed = True
    def close(self):
        self.closed = True


@pytest.fixture
def persistencia_cadastro_premium(monkeypatch):
    connection = CaptureConnection()
    monkeypatch.setattr(backend, "conectar_db", lambda: connection)
    monkeypatch.setattr(backend, "buscar_usuario_por_email", lambda email: None)
    monkeypatch.setattr(backend, "gerar_hash_senha", lambda senha: "hash")
    monkeypatch.setattr(backend, "criar_token", lambda payload: "token")
    monkeypatch.setattr(backend, "registrar_acesso", lambda *args: None)
    backend.cadastro(cadastro_request(plano="premium"))
    values = re.search(
        r"VALUES \(\s*%s, %s, %s, '([^']+)', (true|false),",
        connection.cursor_instance.query,
        flags=re.IGNORECASE,
    )
    assert values is not None, "INSERT deve fixar plano e is_admin no SQL executado"
    return connection, values


def test_payload_premium_persiste_plano_gratuito(persistencia_cadastro_premium):
    connection, values = persistencia_cadastro_premium
    assert values.group(1) == "gratuito"
    assert "premium" not in connection.cursor_instance.params
    assert connection.committed is True


def test_novo_usuario_persiste_is_admin_false(persistencia_cadastro_premium):
    _, values = persistencia_cadastro_premium
    assert values.group(2).lower() == "false"


def test_datas_versoes_e_campos_antigos_persistidos(monkeypatch):
    connection = CaptureConnection()
    monkeypatch.setattr(backend, "conectar_db", lambda: connection)
    backend.criar_usuario(
        "Maria", "maria@example.com", "hash", True, True,
        "2026-07-15", "2026-07-15",
    )
    query = connection.cursor_instance.query
    assert "aceite_termos, versao_termos, data_aceite_termos" in query
    assert "terms_version, terms_accepted_at" in query
    assert "privacy_version, privacy_accepted_at" in query
    assert query.count("now()") == 3
    assert connection.cursor_instance.params == (
        "Maria", "maria@example.com", "hash",
        True, "2026-07-15", True,
        "2026-07-15", True,
        "2026-07-15", True,
    )


def test_insert_legado_persiste_plano_admin_aceites_versoes_e_datas(monkeypatch):
    connection = CaptureConnection()
    monkeypatch.setattr(backend, "conectar_db", lambda: connection)
    monkeypatch.setattr(backend, "buscar_usuario_por_email", lambda email: None)
    monkeypatch.setattr(backend, "gerar_hash_senha", lambda senha: "hash")
    monkeypatch.setattr(backend, "criar_token", lambda payload: "token")
    monkeypatch.setattr(backend, "registrar_acesso", lambda *args: None)

    backend.cadastro(cadastro_legado_request(plano="premium"))

    query = connection.cursor_instance.query
    values = re.search(
        r"VALUES \(\s*%s, %s, %s, '([^']+)', (true|false),",
        query,
        flags=re.IGNORECASE,
    )
    assert values is not None
    assert values.group(1) == "gratuito"
    assert values.group(2).lower() == "false"
    assert query.count("now()") == 3
    assert connection.cursor_instance.params == (
        None,
        "legado@example.com",
        "hash",
        True,
        "beta-2026-07",
        True,
        "beta-2026-07",
        True,
        "beta-2026-07",
        True,
    )


def test_get_me_retorna_full_name(monkeypatch):
    monkeypatch.setattr(backend, "listar_providers_configurados", lambda user_id: ["aws"])
    result = backend.meus_dados({
        "id": 7, "full_name": "Maria", "email": "maria@example.com",
        "plano": "gratuito", "is_admin": False,
    })
    assert result["full_name"] == "Maria"


def test_get_me_aceita_usuario_antigo_sem_full_name(monkeypatch):
    monkeypatch.setattr(backend, "listar_providers_configurados", lambda user_id: [])
    result = backend.meus_dados({
        "id": 7, "full_name": None, "email": "antigo@example.com",
        "plano": "gratuito", "is_admin": False,
    })
    assert result["full_name"] is None


def test_get_me_mantem_campos_existentes(monkeypatch):
    monkeypatch.setattr(backend, "listar_providers_configurados", lambda user_id: ["aws", "gcp"])
    result = backend.meus_dados({
        "id": 7, "full_name": None, "email": "antigo@example.com",
        "plano": "popular", "is_admin": True,
    })
    assert result == {
        "full_name": None,
        "email": "antigo@example.com",
        "plano": "popular",
        "is_admin": True,
        "providers_configurados": ["aws", "gcp"],
    }


def test_openapi_contem_novos_campos_e_schema_explicito_de_me():
    schema = backend.app.openapi()
    cadastro_schema = schema["components"]["schemas"]["CadastroRequest"]
    required = set(cadastro_schema["required"])
    assert {"email", "senha", "aceite_termos"} <= required
    for field in ("full_name", "aceite_privacidade", "terms_version", "privacy_version"):
        assert "contrato novo" in cadastro_schema["properties"][field]["description"]
    legado = cadastro_schema["properties"]["versao_termos"]
    assert "Temporario" in legado["description"]
    assert "legado" in legado["description"]
    me_response = schema["paths"]["/me"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert me_response["$ref"].endswith("/MeResponse")
    me_schema = schema["components"]["schemas"]["MeResponse"]["properties"]
    assert set(me_schema) == {
        "full_name", "email", "plano", "is_admin", "providers_configurados",
    }


class FrontendParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = {}
        self.inputs = {}
        self.labels_for = set()
        self.buttons = {}
        self.links = {}
        self.select_ids = set()
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if tag == "form" and element_id:
            self.forms[element_id] = attributes
        elif tag == "input" and element_id:
            self.inputs[element_id] = attributes
        elif tag == "label" and attributes.get("for"):
            self.labels_for.add(attributes["for"])
        elif tag == "button" and element_id:
            self.buttons[element_id] = attributes
        elif tag == "select" and element_id:
            self.select_ids.add(element_id)
        elif tag == "a":
            href = attributes.get("href")
            if href in {"https://nano-iaas.com.br/termos", "https://nano-iaas.com.br/privacidade"}:
                self.links[href] = attributes

    def handle_data(self, data):
        self.text_parts.append(data)


def frontend_html():
    return (Path(__file__).parents[1] / "docs" / "index.html").read_text()


def frontend_parser(html):
    parser = FrontendParser()
    parser.feed(html)
    return parser


def cadastro_source(html):
    return html[
        html.index("async function fazerCadastro()"):
        html.index("async function exibirConfiguracoes()")
    ]


@pytest.mark.frontend_static
def test_frontend_cadastro_usa_form_e_campos_acessiveis():
    html = frontend_html()
    parser = frontend_parser(html)
    assert "auth-form" in parser.forms
    assert '<link rel="icon" href="./logo.svg" type="image/svg+xml">' in html
    assert parser.buttons["btn-submit-auth"]["type"] == "submit"
    assert parser.inputs["input-email"]["type"] == "email"
    assert parser.inputs["input-email"]["autocomplete"] == "email"
    assert parser.inputs["input-usuario"]["type"] == "text"
    assert parser.inputs["input-usuario"]["autocomplete"] == "username"
    assert parser.inputs["input-senha"]["autocomplete"] == "current-password"
    assert {
        "input-full-name", "input-usuario", "input-email", "input-senha",
        "input-aceite-termos", "input-aceite-privacidade",
    } <= parser.labels_for
    assert parser.inputs["input-aceite-termos"]["type"] == "checkbox"
    assert parser.inputs["input-aceite-privacidade"]["type"] == "checkbox"
    assert "input-plano" not in parser.inputs
    assert "input-plano" not in parser.select_ids


@pytest.mark.frontend_static
def test_frontend_aceites_legais_sao_independentes():
    html = frontend_html()
    parser = frontend_parser(html)
    normalized_text = " ".join("".join(parser.text_parts).split())
    assert "Li e aceito os Termos de Uso." in normalized_text
    assert "Li e aceito a Política de Privacidade." in normalized_text
    assert "Li e aceito os Termos de Uso e a Política de Privacidade." not in normalized_text
    assert set(parser.links) == {
        "https://nano-iaas.com.br/termos",
        "https://nano-iaas.com.br/privacidade",
    }
    for attributes in parser.links.values():
        assert attributes["target"] == "_blank"
        assert set(attributes["rel"].split()) == {"noopener", "noreferrer"}

    source = cadastro_source(html)
    assert 'const aceiteTermos = document.getElementById("input-aceite-termos").checked;' in source
    assert 'const aceitePrivacidade = document.getElementById("input-aceite-privacidade").checked;' in source
    assert re.search(
        r'if \(!aceiteTermos\) \{.*?aceite os Termos de Uso\..*?return;',
        source,
        flags=re.DOTALL,
    )
    assert re.search(
        r'if \(!aceitePrivacidade\) \{.*?aceite a Política de Privacidade\..*?return;',
        source,
        flags=re.DOTALL,
    )


@pytest.mark.frontend_static
def test_frontend_payload_cadastro_separa_aceites_e_omite_plano():
    html = frontend_html()
    source = cadastro_source(html)
    assert "aceite_termos: aceiteTermos" in source
    assert "aceite_privacidade: aceitePrivacidade" in source
    assert 'terms_version: "2026-07-15"' in source
    assert 'privacy_version: "2026-07-15"' in source
    assert "plano," not in source
    assert "input-plano" not in source
    assert '.value.trim().toLowerCase()' in source
    assert "me.full_name || me.email" in html


@pytest.mark.frontend_static
def test_frontend_submit_evitar_duplicidade_e_preserva_enter():
    html = frontend_html()
    assert 'document.getElementById("auth-form").addEventListener("submit", enviarFormularioAuth);' in html
    assert "event.preventDefault();" in html
    assert "if (envioAuthEmAndamento) return;" in html
    assert "botao.disabled = true;" in html
    assert "botao.disabled = false;" in html
    assert "onkeydown=" not in html


@pytest.mark.frontend_static
def test_frontend_modos_cadastro_e_login_permanecem_separados():
    html = frontend_html()
    assert "function alternarModoCadastro()" in html
    assert "function alternarModoLogin()" in html
    assert 'document.getElementById("campo-usuario").style.display = "none"' in html
    assert 'document.getElementById("campo-email").style.display = "block"' in html
    assert 'document.getElementById("campo-usuario").style.display = "block"' in html
    assert 'document.getElementById("campo-email").style.display = "none"' in html
    assert 'document.getElementById("input-senha").autocomplete = "new-password"' in html
    assert 'document.getElementById("input-senha").autocomplete = "current-password"' in html
    login_source = html[html.index("async function fazerLogin()"):html.index("function fazerLogout()")]
    assert "input-usuario" in login_source
    assert "input-email" not in login_source

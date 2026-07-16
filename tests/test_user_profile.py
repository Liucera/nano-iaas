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
    assert {
        "full_name", "email", "senha", "aceite_termos", "aceite_privacidade",
        "terms_version", "privacy_version",
    } <= required
    me_response = schema["paths"]["/me"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert me_response["$ref"].endswith("/MeResponse")
    me_schema = schema["components"]["schemas"]["MeResponse"]["properties"]
    assert set(me_schema) == {
        "full_name", "email", "plano", "is_admin", "providers_configurados",
    }


class LegalLinksParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attributes = dict(attrs)
            href = attributes.get("href")
            if href in {"https://nano-iaas.com.br/termos", "https://nano-iaas.com.br/privacidade"}:
                self.links[href] = attributes

    def handle_data(self, data):
        self.text_parts.append(data)


def test_frontend_contrato_legal_links_payload_e_fallback():
    html = (Path(__file__).parents[1] / "docs" / "index.html").read_text()
    parser = LegalLinksParser()
    parser.feed(html)
    normalized_text = " ".join("".join(parser.text_parts).split())
    assert "Li e aceito os Termos de Uso e a Política de Privacidade." in normalized_text
    assert set(parser.links) == {"https://nano-iaas.com.br/termos", "https://nano-iaas.com.br/privacidade"}
    for attributes in parser.links.values():
        assert attributes["target"] == "_blank"
        assert set(attributes["rel"].split()) == {"noopener", "noreferrer"}
    cadastro_source = html[html.index("async function fazerCadastro()"):html.index("async function exibirConfiguracoes()")]
    for field in ("aceite_termos", "aceite_privacidade", "terms_version", "privacy_version"):
        assert re.search(rf"\b{field}\s*:", cadastro_source)
    assert '"2026-07-15"' in cadastro_source
    assert "me.full_name || me.email" in html


def test_frontend_alterna_visibilidade_do_nome_por_modo():
    html = (Path(__file__).parents[1] / "docs" / "index.html").read_text()
    assert 'id="campo-full-name"' in html
    assert 'style="display:none"' in html
    assert "function alternarModoCadastro()" in html
    assert "function alternarModoLogin()" in html
    assert 'campoNome.style.display = "block"' in html
    assert 'campoNome.style.display = "none"' in html
    assert 'document.getElementById("input-full-name").value = ""' in html
    assert "if (modoCadastro)" in html
    assert "fazerCadastro();" in html

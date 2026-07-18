from pathlib import Path

import pytest


FRONTEND = Path(__file__).parents[1] / "docs" / "index.html"


@pytest.mark.frontend_static
def test_frontend_has_secure_gcp_form_and_empty_state():
    html = FRONTEND.read_text()
    assert "Nenhuma credencial GCP cadastrada." in html
    assert 'id="gcp-service-account-json"' in html
    assert 'name="service_account_json"' in html
    assert 'autocomplete="off"' in html
    assert 'spellcheck="false"' in html
    assert "salvarCredencialGCPPrompt" not in html


@pytest.mark.frontend_static
def test_frontend_supports_create_replace_delete_and_confirmation():
    html = FRONTEND.read_text()
    source = html[
        html.index("async function salvarCredencialGCP"):
        html.index("function exibirFormularioAlterarSenha")
    ]
    assert 'method: substituir ? "PUT" : "POST"' in source
    assert 'apiFetch("/credenciais/gcp", { method: "DELETE" })' in source
    assert 'confirm("Excluir a credencial GCP cadastrada?' in source
    assert "exclusaoCredencialGCPEmAndamento" in source


@pytest.mark.frontend_static
def test_frontend_prevents_duplicate_submission_and_clears_json():
    html = FRONTEND.read_text()
    source = html[
        html.index("async function salvarCredencialGCP"):
        html.index("async function excluirCredencialGCP")
    ]
    assert "if (envioCredencialGCPEmAndamento) return;" in source
    assert "botao.disabled = true;" in source
    assert "form.reset();" in source
    assert "localStorage.setItem" not in source
    assert "sessionStorage.setItem" not in source


@pytest.mark.frontend_static
def test_frontend_never_repopulates_or_persists_service_account_json():
    html = FRONTEND.read_text()
    source = html[
        html.index("async function carregarCredenciaisGCP"):
        html.index("function exibirFormularioAlterarSenha")
    ]
    assert "serviceAccountJson" in source
    assert ".value = serviceAccountJson" not in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source


@pytest.mark.frontend_static
def test_frontend_renders_only_safe_server_metadata_as_text():
    html = FRONTEND.read_text()
    source = html[
        html.index("async function carregarCredenciaisGCP"):
        html.index("function exibirFormularioCredencialGCP")
    ]
    assert "project_id" in source
    assert "client_email_masked" in source
    assert ".textContent =" in source
    assert "private_key" not in source
    assert "private_key_id" not in source
    assert "service_account_json" not in source

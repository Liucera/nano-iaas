from pathlib import Path

import pytest


FRONTEND = Path(__file__).parents[1] / "docs" / "index.html"


@pytest.mark.frontend_static
def test_frontend_has_secure_aws_form_and_empty_state():
    html = FRONTEND.read_text()
    assert "Nenhuma credencial AWS cadastrada." in html
    assert 'id="aws-access-key-id"' in html
    assert 'id="aws-secret-access-key"' in html
    assert 'name="secret_access_key" type="password"' in html
    assert 'autocomplete="off"' in html
    assert "salvarCredencialAWSPrompt" not in html


@pytest.mark.frontend_static
def test_frontend_supports_create_replace_delete_and_confirmation():
    html = FRONTEND.read_text()
    assert 'method: substituir ? "PUT" : "POST"' in html
    assert 'apiFetch("/credenciais/aws", { method: "DELETE" })' in html
    assert 'confirm("Excluir a credencial AWS cadastrada?' in html
    assert "exclusaoCredencialAWSEmAndamento" in html


@pytest.mark.frontend_static
def test_frontend_prevents_duplicate_submission_and_clears_secrets():
    html = FRONTEND.read_text()
    source = html[
        html.index("async function salvarCredencialAWS"):
        html.index("async function excluirCredencialAWS")
    ]
    assert "if (envioCredencialAWSEmAndamento) return;" in source
    assert "botao.disabled = true;" in source
    assert "form.reset();" in source
    assert "localStorage.setItem" not in source
    assert "sessionStorage.setItem" not in source


@pytest.mark.frontend_static
def test_frontend_renders_only_masked_server_values_as_text():
    html = FRONTEND.read_text()
    source = html[
        html.index("async function carregarCredenciaisAWS"):
        html.index("function exibirFormularioCredencialAWS")
    ]
    assert "access_key_id_masked" in source
    assert "secret_access_key_masked" in source
    assert ".textContent =" in source
    assert "access_key_id;" not in source
    assert "secret_access_key;" not in source

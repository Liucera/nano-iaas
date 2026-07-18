from pathlib import Path

import pytest


FRONTEND = Path(__file__).parents[1] / "docs" / "index.html"


@pytest.mark.frontend_static
def test_frontend_has_dedicated_secure_azure_form_without_legacy_prompt():
    html = FRONTEND.read_text()
    for field in ("tenant_id", "client_id", "client_secret", "subscription_id"):
        assert f'name="{field}"' in html
    assert 'id="azure-client-secret"' in html
    assert 'type="password"' in html
    assert "salvarCredencialAzurePrompt" not in html
    assert 'prompt("Azure connection string")' not in html
    assert "Nenhuma credencial Azure cadastrada." in html


@pytest.mark.frontend_static
def test_frontend_azure_crud_is_safe_and_confirmed():
    html = FRONTEND.read_text()
    source = html[html.index("async function carregarCredenciaisAzure"):html.index("function exibirFormularioAlterarSenha")]
    assert 'method: substituir ? "PUT" : "POST"' in source
    assert 'apiFetch("/credenciais/azure", { method: "DELETE" })' in source
    assert 'confirm("Excluir a credencial Azure cadastrada?' in source
    assert "if (envioCredencialAzureEmAndamento) return;" in source
    assert "if (exclusaoCredencialAzureEmAndamento) return;" in source
    assert "form.reset();" in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source


@pytest.mark.frontend_static
def test_frontend_never_repopulates_secret_and_renders_only_masked_metadata():
    html = FRONTEND.read_text()
    listing = html[html.index("async function carregarCredenciaisAzure"):html.index("function exibirFormularioCredencialAzure")]
    assert "tenant_id_masked" in listing
    assert "client_id_masked" in listing
    assert "subscription_id_masked" in listing
    assert ".textContent =" in listing
    assert "client_secret" not in listing
    form = html[html.index("function exibirFormularioCredencialAzure"):html.index("async function excluirCredencialAzure")]
    assert ".value = clientSecret" not in form
    assert "localStorage" not in form
    assert "sessionStorage" not in form

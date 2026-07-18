from pathlib import Path

import pytest


FRONTEND = Path(__file__).parents[1] / "docs" / "index.html"


@pytest.mark.frontend_static
def test_frontend_has_dedicated_plan_interface_without_legacy_prompts():
    html = FRONTEND.read_text()
    assert 'id="plan-update-container"' in html
    assert 'id="plan-update-select"' in html
    assert 'id="plano-atual"' in html
    assert "atualizarPlanoPrompt" not in html
    assert "solicitarPixPrompt" not in html
    assert 'prompt("Plano:' not in html


@pytest.mark.frontend_static
def test_frontend_uses_only_server_options_and_existing_pix_flow():
    html = FRONTEND.read_text()
    source = html[html.index("async function exibirAtualizacaoPlano"):html.index("function formatDate")]
    assert 'apiFetch("/me/plano/opcoes")' in source
    assert "configuracao.opcoes.forEach" in source
    assert 'apiFetch("/pix")' in source
    assert 'apiFetch("/pix/solicitacao"' in source
    assert 'apiFetch("/me/plano"' in source
    assert "popular" not in source
    assert "premium" not in source


@pytest.mark.frontend_static
def test_frontend_confirms_prevents_duplicates_and_refreshes_visual_state():
    html = FRONTEND.read_text()
    source = html[html.index("async function salvarAtualizacaoPlano"):html.index("function formatDate")]
    assert "if (envioPlanoEmAndamento) return;" in source
    assert "botao.disabled = true;" in source
    assert "confirm(`Confirmar a operação" in source
    assert "const solicitarPix = pago && plano !== form.dataset.planoAtual;" in source
    assert "comprovante.hidden = !pago || mesmoPlano;" in html
    assert "form.reset();" in source
    assert "await exibirConfiguracoes();" in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source


@pytest.mark.frontend_static
def test_frontend_never_sends_user_or_admin_fields():
    html = FRONTEND.read_text()
    source = html[html.index("async function salvarAtualizacaoPlano"):html.index("function formatDate")]
    assert "user_id" not in source
    assert "is_admin" not in source
    assert "email:" not in source

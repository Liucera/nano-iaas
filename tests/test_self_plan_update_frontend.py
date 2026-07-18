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
    assert "const opcoesDestino = configuracao.opcoes.filter(" in source
    assert "(opcao) => opcao.plano !== configuracao.plano_atual" in source
    assert "opcoesDestino.forEach" in source
    assert "select.value = configuracao.plano_atual" not in source
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


@pytest.mark.frontend_static
def test_frontend_keeps_current_plan_visible_but_out_of_destination_options():
    html = FRONTEND.read_text()
    account = html[
        html.index("async function exibirConfiguracoes"):
        html.index("async function carregarCredenciaisAWS")
    ]
    options = html[
        html.index("async function exibirAtualizacaoPlano"):
        html.index("async function salvarAtualizacaoPlano")
    ]
    assert '<strong id="plano-atual"></strong>' in account
    assert 'document.getElementById("plano-atual").textContent = me.plano;' in account
    assert "opcao.plano !== configuracao.plano_atual" in options
    assert "opcoesDestino.forEach" in options


@pytest.mark.frontend_static
def test_frontend_blocks_manipulated_current_plan_before_confirmation_or_api_call():
    html = FRONTEND.read_text()
    source = html[
        html.index("async function salvarAtualizacaoPlano"):
        html.index("function formatDate")
    ]
    guard = source.index("if (plano === form.dataset.planoAtual)")
    controlled_message = source.index("Selecione um plano diferente do plano atual.")
    confirmation = source.index("confirm(`Confirmar a operação")
    pix_call = source.index('apiFetch("/pix/solicitacao"')
    direct_call = source.index('apiFetch("/me/plano"')
    assert guard < controlled_message < confirmation < pix_call < direct_call
    assert "return;" in source[guard:confirmation]


@pytest.mark.frontend_static
def test_frontend_preserves_free_downgrade_paid_pix_and_cancel_without_submission():
    html = FRONTEND.read_text()
    rendering = html[
        html.index("const atualizarDetalhes"):
        html.index("async function salvarAtualizacaoPlano")
    ]
    submission = html[
        html.index("async function salvarAtualizacaoPlano"):
        html.index("function formatDate")
    ]
    cancel = rendering[
        rendering.index('document.getElementById("plan-update-cancel")'):
        rendering.index("atualizarDetalhes();")
    ]
    assert 'modoAtivacao === "pix_aprovacao_manual"' in rendering
    assert "O plano gratuito pode ser ativado diretamente." in rendering
    assert "A ativação exige pagamento PIX e aprovação manual." in rendering
    assert 'apiFetch("/pix/solicitacao"' in submission
    assert 'apiFetch("/me/plano"' in submission
    assert "form.reset();" in cancel
    assert 'container.innerHTML = "";' in cancel
    assert "apiFetch(" not in cancel

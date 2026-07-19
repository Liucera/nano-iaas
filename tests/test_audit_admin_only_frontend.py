import json
import re
import subprocess
from pathlib import Path

import pytest


FRONTEND = Path(__file__).parents[1] / "docs" / "index.html"


def audit_javascript_source():
    html = FRONTEND.read_text()
    visibility = html[
        html.index("function aplicarVisibilidadeAuditoria"):
        html.index("    if (token) {")
    ]
    logout = html[
        html.index("function fazerLogout()"):
        html.index("function atualizarContadores()")
    ]
    return visibility + "\n" + logout


AUDIT_HARNESS = r"""
const assert = require("node:assert/strict");
const scenario = JSON.parse(process.argv[1]);
const source = process.argv[2];

const execute = new Function("assert", "scenario", "source", `
  const elements = new Map([
    ["sidebar-audit-link", { hidden: true, style: {}, value: "" }],
    ["toolbar-audit-link", { hidden: true, style: {}, value: "" }],
  ]);
  const document = {
    getElementById(id) {
      if (!elements.has(id)) {
        elements.set(id, { hidden: true, style: {}, value: "" });
      }
      return elements.get(id);
    },
  };
  const removedSessionKeys = [];
  const sessionStorage = {
    removeItem(key) {
      removedSessionKeys.push(key);
    },
  };
  let token = "token-a";
  let resolveMe = null;
  let apiCalls = 0;
  const apiFetch = (path) => {
    assert.equal(path, "/me");
    apiCalls += 1;
    if (scenario.kind === "error") {
      return Promise.reject(new Error("simulated /me failure"));
    }
    if (scenario.kind === "pending_logout") {
      return new Promise((resolve) => {
        resolveMe = resolve;
      });
    }
    return Promise.resolve(scenario.me);
  };

  eval(source);

  return (async () => {
    const sidebar = document.getElementById("sidebar-audit-link");
    const toolbar = document.getElementById("toolbar-audit-link");

    if (scenario.kind === "logout_immediate") {
      aplicarVisibilidadeAuditoria(true);
      assert.equal(sidebar.hidden, false);
      assert.equal(toolbar.hidden, false);
      fazerLogout();
      assert.equal(sidebar.hidden, true);
      assert.equal(toolbar.hidden, true);
      assert.equal(token, null);
      assert.deepEqual(removedSessionKeys, ["nano_iaas_token"]);
      return { sidebar: sidebar.hidden, toolbar: toolbar.hidden, apiCalls };
    }

    if (scenario.kind === "pending_logout") {
      const pending = atualizarVisibilidadeAuditoria();
      assert.equal(apiCalls, 1);
      assert.equal(typeof resolveMe, "function");
      fazerLogout();
      assert.equal(sidebar.hidden, true);
      assert.equal(toolbar.hidden, true);
      resolveMe({ is_admin: true });
      const result = await pending;
      assert.equal(result, null);
      assert.equal(sidebar.hidden, true);
      assert.equal(toolbar.hidden, true);
      return { sidebar: sidebar.hidden, toolbar: toolbar.hidden, apiCalls };
    }

    const result = await atualizarVisibilidadeAuditoria();
    assert.equal(apiCalls, 1);
    if (scenario.kind === "error") {
      assert.equal(result, null);
      assert.equal(sidebar.hidden, true);
      assert.equal(toolbar.hidden, true);
    } else {
      assert.deepEqual(result, scenario.me);
      const visible = scenario.me.is_admin === true;
      assert.equal(sidebar.hidden, !visible);
      assert.equal(toolbar.hidden, !visible);
    }
    return { sidebar: sidebar.hidden, toolbar: toolbar.hidden, apiCalls };
  })();
`);

Promise.resolve(execute(assert, scenario, source))
  .then((result) => process.stdout.write(JSON.stringify(result)))
  .catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
"""


def run_audit_scenario(scenario):
    result = subprocess.run(
        ["node", "-e", AUDIT_HARNESS, json.dumps(scenario), audit_javascript_source()],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.frontend_static
def test_audit_controls_have_ids_start_hidden_and_hidden_css_is_strict():
    html = FRONTEND.read_text()
    for control_id in ("sidebar-audit-link", "toolbar-audit-link"):
        control = re.search(
            rf'<button(?=[^>]*id="{control_id}")(?=[^>]*\shidden(?:\s|>))[^>]*>',
            html,
        )
        assert control is not None
    assert "[hidden] { display: none !important; }" in html


@pytest.mark.frontend_static
def test_audit_visibility_structure_requires_admin_and_current_token():
    source = audit_javascript_source()
    assert "function aplicarVisibilidadeAuditoria(isAdmin = false)" in source
    assert "const visivel = isAdmin === true;" in source
    assert '["sidebar-audit-link", "toolbar-audit-link"]' in source
    assert "controle.hidden = !visivel;" in source
    assert "const tokenConsultado = token;" in source
    assert "tokenConsultado !== token" in source
    assert "return me;" in source
    assert "return null;" in source


@pytest.mark.frontend_static
def test_signup_reuses_validated_me_without_second_request():
    html = FRONTEND.read_text()
    signup = html[
        html.index("async function fazerCadastro()"):
        html.index("async function exibirConfiguracoes")
    ]
    settings = html[
        html.index("async function exibirConfiguracoes"):
        html.index("async function carregarCredenciaisAWS")
    ]
    assert "const me = await atualizarVisibilidadeAuditoria();" in signup
    assert "if (me !== null)" in signup
    assert "await exibirConfiguracoes(me);" in signup
    assert 'apiFetch("/me")' not in signup
    assert "async function exibirConfiguracoes(meValidado = null)" in settings
    assert 'meValidado !== null ? meValidado : await apiFetch("/me")' in settings


@pytest.mark.frontend_static
def test_session_restore_and_login_refresh_audit_visibility():
    html = FRONTEND.read_text()
    restore = html[
        html.index("    if (token) {"):
        html.index("function setStatus")
    ]
    login = html[
        html.index("async function fazerLogin()"):
        html.index("function fazerLogout()")
    ]
    expected = "await atualizarVisibilidadeAuditoria();"
    assert expected in restore
    assert expected in login


@pytest.mark.frontend_static
def test_logout_hides_before_clearing_token_structure():
    source = audit_javascript_source()
    logout = source[source.index("function fazerLogout()"):]
    hide = logout.index("aplicarVisibilidadeAuditoria(false);")
    clear_token = logout.index("token = null;")
    assert hide < clear_token


@pytest.mark.frontend_static
def test_admin_response_shows_both_audit_controls():
    result = run_audit_scenario({"kind": "resolved", "me": {"is_admin": True}})
    assert result == {"sidebar": False, "toolbar": False, "apiCalls": 1}


@pytest.mark.frontend_static
def test_common_user_response_keeps_both_audit_controls_hidden():
    result = run_audit_scenario({"kind": "resolved", "me": {"is_admin": False}})
    assert result == {"sidebar": True, "toolbar": True, "apiCalls": 1}


@pytest.mark.frontend_static
def test_me_error_keeps_both_audit_controls_hidden():
    result = run_audit_scenario({"kind": "error"})
    assert result == {"sidebar": True, "toolbar": True, "apiCalls": 1}


@pytest.mark.frontend_static
def test_late_admin_response_after_logout_does_not_show_controls():
    result = run_audit_scenario({"kind": "pending_logout"})
    assert result == {"sidebar": True, "toolbar": True, "apiCalls": 1}


@pytest.mark.frontend_static
def test_logout_hides_controls_immediately():
    result = run_audit_scenario({"kind": "logout_immediate"})
    assert result == {"sidebar": True, "toolbar": True, "apiCalls": 0}

import inspect
import os

import pytest

os.environ.setdefault("NANO_IAAS_SECRET_KEY", "audit-hardening-test-secret")
os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "audit-hardening-encryption-key")

from web.backend import main as backend


class FakeCursor:
    def __init__(self):
        self.query = None
        self.params = None

    def execute(self, query, params):
        self.query = " ".join(query.split())
        self.params = params


def test_audit_details_are_sanitized_and_limited():
    raw = (
        "token=eyJabc.def.ghi;"
        "secret_access_key=super-secret;"
        "linha\nnova"
    )
    sanitized = backend.sanitizar_detalhes_auditoria(raw)

    assert "eyJabc.def.ghi" not in sanitized
    assert "super-secret" not in sanitized
    assert "[REDACTED]" in sanitized
    assert "\n" not in sanitized
    assert len(sanitized) <= backend.AUDIT_TEXT_MAX_LENGTH


def test_central_audit_insert_uses_only_sanitized_values():
    cursor = FakeCursor()
    backend.inserir_evento_auditoria(
        cursor,
        "user@example.invalid",
        "TEST",
        provider="aws",
        recurso="bucket",
        detalhes="client_secret=do-not-log",
    )

    assert "INSERT INTO audit_log" in cursor.query
    assert cursor.params[:4] == (
        "user@example.invalid",
        "TEST",
        "aws",
        "bucket",
    )
    assert cursor.params[4] == "[REDACTED]"


@pytest.mark.parametrize(
    ("limite", "deslocamento"),
    [
        (0, 0),
        (101, 0),
        (True, 0),
        (50, -1),
        (50, True),
    ],
)
def test_audit_query_rejects_invalid_pagination(limite, deslocamento):
    with pytest.raises(ValueError):
        backend.buscar_logs_auditoria(limite, deslocamento)


def test_audit_sql_is_centralized():
    module_source = inspect.getsource(backend)
    helper_source = inspect.getsource(backend.inserir_evento_auditoria)

    assert helper_source.count("INSERT INTO audit_log") == 2
    assert module_source.count("INSERT INTO audit_log") == (
        helper_source.count("INSERT INTO audit_log")
    )

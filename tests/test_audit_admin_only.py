import os
import sys
import types

import pydantic
import pytest
from fastapi import HTTPException


os.environ.setdefault("NANO_IAAS_SECRET_KEY", "audit-admin-only-test-secret")
os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "audit-admin-only-encryption-key")

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


COMMON_USER = {
    "id": 81,
    "email": "common-audit-user@example.invalid",
    "is_admin": False,
}
ADMIN_USER = {
    "id": 1,
    "email": "admin-audit-user@example.invalid",
    "is_admin": True,
}


def test_common_user_receives_403(monkeypatch):
    monkeypatch.setattr(
        backend,
        "buscar_logs_auditoria",
        lambda limite=50: pytest.fail("audit lookup must not run for common users"),
    )

    with pytest.raises(HTTPException) as error:
        backend.ver_logs(COMMON_USER)

    assert error.value.status_code == 403


def test_common_user_does_not_query_audit_logs(monkeypatch):
    calls = []

    def buscar_logs(limite=50):
        calls.append(limite)
        return []

    monkeypatch.setattr(backend, "buscar_logs_auditoria", buscar_logs)

    with pytest.raises(HTTPException):
        backend.ver_logs(COMMON_USER)

    assert calls == []


def test_admin_receives_audit_logs(monkeypatch):
    expected_logs = [{"acao": "LOGIN", "provider": "-", "recurso": "-"}]
    calls = []
    monkeypatch.setattr(
        backend,
        "buscar_logs_auditoria",
        lambda limite=50: calls.append(limite) or expected_logs,
    )

    assert backend.ver_logs(ADMIN_USER) == {"logs": expected_logs}
    assert calls == [50]

import asyncio
import inspect
import os
from uuid import UUID

import pytest
from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import jwt

os.environ.setdefault("NANO_IAAS_SECRET_KEY", "security-hardening-test-secret")
os.environ.setdefault("NANO_IAAS_ENCRYPTION_KEY", "security-hardening-test-encryption-key")

from web.backend import main as backend


def _request(path="/health"):
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    })


def test_security_headers_are_applied():
    async def call_next(_request):
        return JSONResponse({"ok": True})

    response = asyncio.run(
        backend.aplicar_headers_seguranca(_request(), call_next)
    )

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )
    assert response.headers["cross-origin-resource-policy"] == "same-site"
    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )


def test_cors_does_not_use_wildcards():
    middleware = next(
        item for item in backend.app.user_middleware
        if item.cls is CORSMiddleware
    )

    assert "*" not in middleware.kwargs["allow_methods"]
    assert "*" not in middleware.kwargs["allow_headers"]
    assert set(middleware.kwargs["allow_methods"]) == {
        "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS",
    }
    assert set(middleware.kwargs["allow_headers"]) == {
        "Authorization", "Content-Type", "Accept",
    }


def test_access_token_has_required_security_claims():
    token = backend.criar_token({
        "sub": "user@example.invalid",
        "uid": 42,
    })
    payload = jwt.decode(
        token,
        backend.SECRET_KEY,
        algorithms=[backend.ALGORITHM],
    )

    assert payload["typ"] == "access"
    assert payload["sub"] == "user@example.invalid"
    assert payload["uid"] == 42
    assert isinstance(payload["iat"], int)
    assert payload["exp"] > payload["iat"]
    UUID(payload["jti"])


def test_token_subject_must_match_database_user(monkeypatch):
    token = backend.criar_token({
        "sub": "attacker@example.invalid",
        "uid": 42,
    })
    monkeypatch.setattr(
        backend,
        "buscar_usuario_por_id",
        lambda _user_id: {
            "id": 42,
            "email": "owner@example.invalid",
            "is_admin": False,
        },
    )

    with pytest.raises(HTTPException) as error:
        backend.usuario_atual(token)

    assert error.value.status_code == 401
    assert error.value.detail == "Token inválido"


def test_admin_bootstrap_has_no_fixed_password_hash():
    source = inspect.getsource(backend.migrar_admin_inicial)

    assert "$2b$12$iFhBXzXNqhksnzFyE5Zky" not in source
    assert "NANO_IAAS_INITIAL_ADMIN_PASSWORD" in source
    assert "pelo menos 12 caracteres" in source

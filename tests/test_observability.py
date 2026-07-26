import asyncio
import json
import logging
import os
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse

os.environ.setdefault(
    "NANO_IAAS_SECRET_KEY",
    "observability-test-secret",
)
os.environ.setdefault(
    "NANO_IAAS_ENCRYPTION_KEY",
    "observability-test-encryption-key",
)

from core.observability import JsonFormatter, normalizar_request_id
from providers.aws import s3_reader as aws_module
from providers.azure import blob_reader as azure_module
from providers.gcp import gcs_reader as gcp_module
from web.backend import main as backend


class CapturingLogger:
    def __init__(self):
        self.records = []

    def _capture(self, level, event, extra):
        self.records.append({
            "level": level,
            "event": event,
            "extra": extra,
        })

    def info(self, event, extra):
        self._capture("INFO", event, extra)

    def warning(self, event, extra):
        self._capture("WARNING", event, extra)

    def error(self, event, extra):
        self._capture("ERROR", event, extra)


def _request(path="/health", request_id=None):
    headers = []
    if request_id is not None:
        headers.append((
            b"x-request-id",
            request_id.encode("utf-8"),
        ))

    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"sensitive=not-logged",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    })


def test_json_formatter_emits_only_allowed_fields():
    sensitive = "secret-access-key-material"
    record = logging.LogRecord(
        "nano_iaas.providers.aws",
        logging.ERROR,
        __file__,
        1,
        "provider_read_failed",
        (),
        None,
    )
    record.request_id = "req-test-123"
    record.provider = "aws"
    record.operation = "read"
    record.secret_access_key = sensitive

    payload = json.loads(JsonFormatter().format(record))
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["event"] == "provider_read_failed"
    assert payload["request_id"] == "req-test-123"
    assert payload["provider"] == "aws"
    assert payload["operation"] == "read"
    assert "secret_access_key" not in payload
    assert sensitive not in serialized


def test_request_id_accepts_safe_value_and_rejects_unsafe_value():
    assert normalizar_request_id("req-ABC_123.test") == (
        "req-ABC_123.test"
    )

    generated = normalizar_request_id(
        "unsafe-request-id\nforged-log"
    )
    UUID(generated)


def test_http_middleware_adds_correlation_and_duration(monkeypatch):
    captured = CapturingLogger()
    monkeypatch.setattr(
        backend,
        "logger_observabilidade_http",
        captured,
    )

    async def call_next(_request):
        return JSONResponse({"ok": True})

    response = asyncio.run(
        backend.registrar_observabilidade_http(
            _request(request_id="req-safe-123"),
            call_next,
        )
    )

    assert response.headers["x-request-id"] == "req-safe-123"
    assert len(captured.records) == 1

    record = captured.records[0]
    assert record["level"] == "INFO"
    assert record["event"] == "http_request_completed"
    assert record["extra"]["method"] == "GET"
    assert record["extra"]["path"] == "/health"
    assert record["extra"]["status_code"] == 200
    assert record["extra"]["duration_ms"] >= 0
    assert "query" not in record["extra"]
    assert "sensitive" not in str(record)


def test_http_middleware_replaces_unsafe_request_id(monkeypatch):
    captured = CapturingLogger()
    monkeypatch.setattr(
        backend,
        "logger_observabilidade_http",
        captured,
    )

    async def call_next(_request):
        return JSONResponse({"ok": True})

    response = asyncio.run(
        backend.registrar_observabilidade_http(
            _request(request_id="unsafe value"),
            call_next,
        )
    )

    UUID(response.headers["x-request-id"])


def test_aws_failure_log_does_not_include_secret(monkeypatch):
    sensitive = "aws-secret-material"
    captured = CapturingLogger()

    def fail_session(**_kwargs):
        raise RuntimeError(sensitive)

    monkeypatch.setattr(aws_module, "logger", captured)
    monkeypatch.setattr(aws_module.boto3, "Session", fail_session)

    reader = aws_module.S3Reader()
    assert reader.authenticate({
        "access_key_id": "test-access-key",
        "secret_access_key": sensitive,
    }) is False

    serialized = json.dumps(captured.records)
    assert sensitive not in serialized
    assert captured.records[0]["extra"]["provider"] == "aws"


def test_gcp_failure_log_does_not_include_secret(monkeypatch):
    sensitive = "gcp-private-material"
    captured = CapturingLogger()

    def fail_client(**_kwargs):
        raise RuntimeError(sensitive)

    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv(
        "GOOGLE_APPLICATION_CREDENTIALS",
        raising=False,
    )
    monkeypatch.setattr(gcp_module, "logger", captured)
    monkeypatch.setattr(gcp_module.storage, "Client", fail_client)

    reader = gcp_module.GCSReader()
    assert reader.authenticate({"project_id": "test-project"}) is False

    serialized = json.dumps(captured.records)
    assert sensitive not in serialized
    assert captured.records[0]["extra"]["provider"] == "gcp"


def test_azure_failure_log_does_not_include_secret(monkeypatch):
    sensitive = "azure-sensitive-connection-string"
    captured = CapturingLogger()

    def fail_connection_string(*_args, **_kwargs):
        raise RuntimeError(sensitive)

    monkeypatch.setattr(azure_module, "logger", captured)
    monkeypatch.setattr(
        azure_module.BlobServiceClient,
        "from_connection_string",
        fail_connection_string,
    )

    reader = azure_module.BlobReader()
    assert reader.authenticate({
        "connection_string": sensitive,
    }) is False

    serialized = json.dumps(captured.records)
    assert sensitive not in serialized
    assert captured.records[0]["extra"]["provider"] == "azure"

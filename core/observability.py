"""Observabilidade estruturada e sanitizada do Nano-IaaS."""

from contextvars import ContextVar, Token
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any
from uuid import uuid4


_REQUEST_ID = ContextVar("nano_iaas_request_id", default="-")
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")
_ALLOWED_EXTRA_FIELDS = (
    "provider",
    "operation",
    "method",
    "path",
    "status_code",
    "duration_ms",
)


class JsonFormatter(logging.Formatter):
    """Formata somente campos controlados em uma linha JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": getattr(
                record,
                "request_id",
                obter_request_id(),
            ),
        }

        for field in _ALLOWED_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is None or isinstance(value, (str, int, float, bool)):
                if value is not None:
                    payload[field] = value

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def configurar_observabilidade() -> None:
    """Configura uma única saída JSON para os loggers do produto."""

    root_logger = logging.getLogger("nano_iaas")
    root_logger.setLevel(logging.INFO)
    root_logger.propagate = False

    if any(
        getattr(handler, "_nano_iaas_json", False)
        for handler in root_logger.handlers
    ):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._nano_iaas_json = True
    root_logger.addHandler(handler)


def obter_logger(component: str) -> logging.Logger:
    return logging.getLogger(f"nano_iaas.{component}")


def normalizar_request_id(value: str | None) -> str:
    if value is not None and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())


def definir_request_id(value: str) -> Token:
    return _REQUEST_ID.set(value)


def restaurar_request_id(token: Token) -> None:
    _REQUEST_ID.reset(token)


def obter_request_id() -> str:
    return _REQUEST_ID.get()


configurar_observabilidade()

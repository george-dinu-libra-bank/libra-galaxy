"""Logging JSON structurat, cu id-uri de corelare si redactare (docs/SECURITY.md #3)."""

from __future__ import annotations

import contextvars
import json
import logging
from datetime import datetime, timezone
from typing import Any

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)

_REDACTED_KEYS = {
    "password", "token", "api_key", "authorization", "iban", "iban_cont",
    "card_number", "numar_card", "ccv", "national_id", "cnp",
    "content", "continut", "message", "answer", "prompt", "raspuns", "intrebare",
}


def _redact(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            key: ("[REDACTED]" if key.lower() in _REDACTED_KEYS else _redact(value))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_redact(item) for item in data]
    return data


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
        }

        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload.update(_redact(event_data))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLineFormatter())
    root.addHandler(handler)


def log_event(logger: logging.Logger, message: str, **event_data: Any) -> None:
    logger.info(message, extra={"event_data": event_data})

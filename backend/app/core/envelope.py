"""Plicul de raspuns standard (docs/API_CONVENTIONS.md #1)."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi.responses import JSONResponse

from app.core.errors import AppError


def new_request_id() -> str:
    return f"req_{secrets.token_hex(8)}"


def success(body: Any, *, message: str = "OK", request_id: str, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "message": message, "body": body, "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


def error_response(error: AppError, *, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "success": False,
            "error": {"code": error.code, "message": error.message, "details": error.details},
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )

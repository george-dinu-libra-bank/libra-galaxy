from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "libra-api"


class ErrorResponse(BaseModel):
    detail: str
    request_id: str | None = None

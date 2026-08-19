from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MesajChat(BaseModel):
    rol: Literal["user", "assistant"]
    continut: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mesaj: str = Field(min_length=1, max_length=4000)
    # Istoricul vine de la client; identitatea NU — aceea se ia din token.
    istoric: list[MesajChat] = Field(default_factory=list, max_length=20)


class ApelTool(BaseModel):
    """Ce capabilitate a cerut agentul. Se intoarce pentru observabilitate (cap. 18)."""

    nume: str
    argumente: dict


class ChatResponse(BaseModel):
    raspuns: str
    tool_uri_folosite: list[ApelTool] = Field(default_factory=list)
    pasi: int


class SoldSumar(BaseModel):
    total_disponibil: float
    valuta: str = "RON"
    numar_carduri: int
    carduri_blocate: int


class LunaCashflow(BaseModel):
    luna: str  # YYYY-MM
    incasari: float
    cheltuieli: float
    net: float


class CashflowResponse(BaseModel):
    valuta: str = "RON"
    luni: list[LunaCashflow]
    media_lunara_cheltuieli: float

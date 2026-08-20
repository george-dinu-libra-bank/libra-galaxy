from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MesajChat(BaseModel):
    rol: Literal["user", "assistant"]
    continut: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    # Identitatea nu vine niciodata de la client: se ia din token.
    model_config = ConfigDict(extra="forbid")

    mesaj: str = Field(min_length=1, max_length=4000)
    istoric: list[MesajChat] = Field(default_factory=list, max_length=20)


class ApelAgent(BaseModel):
    """Cine a fost chemat si ce a folosit. Pentru observabilitate si depanare."""

    agent: str
    disponibil: bool
    tool_uri: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    raspuns: str
    agenti: list[ApelAgent] = Field(default_factory=list)
    pasi: int

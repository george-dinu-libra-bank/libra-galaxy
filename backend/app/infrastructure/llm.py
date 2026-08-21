"""Accesul la model, in spatele unei interfete.

Furnizorul activ e Azure AI Foundry (`gpt-5-mini`). Interfata exista ca sa nu fie
nevoie sa se rescrie agentii cand se schimba furnizorul: doar clasa de aici.

SDK-ul azure-ai-inference e sincron, deci apelurile se muta pe alt fir cu
anyio, ca sa nu blocheze bucla de evenimente a FastAPI.
"""

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from anyio import to_thread

from app.infrastructure.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CerereTool:
    """Un tool pe care modelul vrea sa il apeleze."""

    id: str
    nume: str
    argumente: dict


@dataclass(frozen=True, slots=True)
class RaspunsModel:
    text: str
    apeluri: list[CerereTool] = field(default_factory=list)

    @property
    def cere_tool(self) -> bool:
        return bool(self.apeluri)


class ClientModel(Protocol):
    model: str

    async def completeaza(
        self, mesaje: list[dict], unelte: list[dict] | None = None
    ) -> RaspunsModel: ...


class ClientAzure:
    """Azure AI Foundry prin azure-ai-inference."""

    def __init__(
        self, endpoint: str, api_key: str, deployment: str, max_tokens: int, auth: str = "key"
    ) -> None:
        from azure.ai.inference import ChatCompletionsClient

        self._client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=_credential(auth, api_key),
            credential_scopes=["https://cognitiveservices.azure.com/.default"],
        )
        self.model = deployment
        self._max_tokens = max_tokens

    async def completeaza(
        self, mesaje: list[dict], unelte: list[dict] | None = None
    ) -> RaspunsModel:
        def apel() -> Any:
            return self._client.complete(
                model=self.model,
                messages=mesaje,
                tools=unelte or None,
                # Familia gpt-5 a redenumit plafonul de iesire; numele vechi da eroare.
                model_extras={"max_completion_tokens": self._max_tokens},
            )

        raspuns = await to_thread.run_sync(apel)
        mesaj = raspuns.choices[0].message

        apeluri = [
            CerereTool(id=apel.id, nume=apel.function.name, argumente=_json(apel.function.arguments))
            for apel in (mesaj.tool_calls or [])
        ]
        return RaspunsModel(text=mesaj.content or "", apeluri=apeluri)


def _credential(auth: str, api_key: str):
    """Cheie sau Entra.

    'identity' cere fie `az login` pe masina, fie managed identity cand aplicatia
    ruleaza in Azure. In containerul de dev nu exista niciuna dintre ele, de aceea
    implicit ramane cheia.
    """
    if auth.lower() == "identity":
        from azure.identity import DefaultAzureCredential

        return DefaultAzureCredential()

    from azure.core.credentials import AzureKeyCredential

    if not api_key:
        raise ValueError("AZURE_AI_AUTH=key, dar AZURE_AI_API_KEY lipseste.")
    return AzureKeyCredential(api_key)


def _json(argumente: str | dict | None) -> dict:
    """Argumentele vin ca text JSON. Un model poate scapa un JSON stricat —
    atunci tool-ul primeste dictionar gol si raspunde ca ii lipsesc datele,
    in loc sa cada tot requestul."""
    if isinstance(argumente, dict):
        return argumente
    if not argumente:
        return {}
    try:
        return json.loads(argumente)
    except json.JSONDecodeError:
        logger.warning("argumente de tool invalide: %r", argumente[:200])
        return {}


def mesaj_asistent(raspuns: RaspunsModel) -> dict:
    """Raspunsul modelului, in forma in care se pune inapoi in istoric."""
    if not raspuns.cere_tool:
        return {"role": "assistant", "content": raspuns.text}
    return {
        "role": "assistant",
        "content": raspuns.text or None,
        "tool_calls": [
            {
                "id": apel.id,
                "type": "function",
                "function": {"name": apel.nume, "arguments": json.dumps(apel.argumente)},
            }
            for apel in raspuns.apeluri
        ],
    }


def mesaj_tool(apel: CerereTool, rezultat: Any) -> dict:
    return {
        "role": "tool",
        "tool_call_id": apel.id,
        "content": json.dumps(rezultat, ensure_ascii=False, default=str),
    }


@lru_cache
def get_client_model() -> ClientModel:
    setari: Settings = get_settings()
    if setari.llm_provider.lower() != "azure":
        raise ValueError(
            f"LLM_PROVIDER='{setari.llm_provider}' nu e suportat inca. Momentan doar 'azure'."
        )
    return ClientAzure(
        endpoint=setari.azure_ai_endpoint,
        api_key=setari.azure_ai_api_key,
        deployment=setari.azure_ai_chat_deployment,
        max_tokens=setari.agent_max_tokens,
        auth=setari.azure_ai_auth,
    )

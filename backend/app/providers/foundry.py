"""Microsoft Foundry — o singura implementare, fara fallback.

Endpoint-ul e cel din Foundry (blade "Models"), forma
`https://<resursa>.openai.azure.com/models` — API-ul unificat compatibil
OpenAI, nu clasicul Azure OpenAI (`AsyncAzureOpenAI`/`azure_endpoint`, care
raspunde 404 pe acest tip de resursa). Se foloseste clientul OpenAI simplu, cu
`base_url` = endpoint-ul Foundry (confirmat live, nu doar din documentatie).

`gpt-5-mini` e un model de reasoning: nu accepta `temperature` diferit de
valoarea implicita (400 `unsupported_value`), si tokenii de reasoning se scad
din acelasi buget ca raspunsul vizibil — de aceea `max_completion_tokens`
trebuie sa fie generos, nu doar cat raspunsul asteptat. `reasoning_effort`
("low", verificat live ca e acceptat de acest deployment) tine consumul de
tokeni invizibili in frau, ca sa nu manance tot bugetul si sa lase raspunsul
vizibil gol — agentii care folosesc acest provider doar explica date deja
calculate determinist, nu au nevoie de reasoning adanc (CLAUDE.md #25).

Daca Foundry nu e configurat sau esueaza, ridica AI_PROVIDER_UNAVAILABLE /
AI_PROVIDER_ERROR — niciodata nu trece silentios pe alt model
(docs/decisions/0003-no-provider-fallback.md).
"""

from __future__ import annotations

import json
import logging

from openai import APIConnectionError, APIError, AsyncOpenAI

from app.core.config import Settings
from app.core.errors import AiProviderError, AiProviderUnavailableError
from app.providers.base import ChatCompletion, ChatMessage, ImagePart, StructuredCompletion

logger = logging.getLogger(__name__)


def _to_openai_content(content):
    if isinstance(content, str):
        return content

    parts = []
    for part in content:
        if isinstance(part, ImagePart):
            parts.append({"type": "image_url", "image_url": {"url": part.data_uri}})
        else:
            parts.append({"type": "text", "text": part})
    return parts


class MicrosoftFoundryChatProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.foundry_configured:
            raise AiProviderUnavailableError("Microsoft Foundry nu este configurat.")

        self.deployment = settings.foundry_chat_deployment
        self._max_completion_tokens = settings.foundry_max_completion_tokens
        self._reasoning_effort = settings.foundry_reasoning_effort
        self._client = AsyncOpenAI(base_url=settings.foundry_endpoint, api_key=settings.foundry_api_key)

    async def complete(self, messages: list[ChatMessage]) -> ChatCompletion:
        try:
            response = await self._client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": message.role, "content": _to_openai_content(message.content)} for message in messages
                ],
                max_completion_tokens=self._max_completion_tokens,
                reasoning_effort=self._reasoning_effort,
            )
        except APIConnectionError as exc:
            raise AiProviderUnavailableError("Microsoft Foundry este inaccesibil.") from exc
        except APIError as exc:
            raise AiProviderError("Microsoft Foundry a raspuns cu o eroare.") from exc

        usage = response.usage
        cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0

        return ChatCompletion(
            text=response.choices[0].message.content or "",
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            tokens_cached=cached,
            deployment=self.deployment,
        )

    async def complete_json(
        self, messages: list[ChatMessage], schema_name: str, schema: dict
    ) -> StructuredCompletion:
        """Ca `complete`, dar cere modelului sa respecte o schema JSON.

        Folosit doar de pipeline-ul AI de credite (app/credit/ai/) — agentii
        conversationali raman pe `complete()`, care intoarce proza. Verificat live
        (2026-08-24, REGULI.md #7): acest deployment accepta `json_schema` +
        `strict: true` si raspunde cu JSON valid.
        """
        try:
            response = await self._client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": message.role, "content": _to_openai_content(message.content)} for message in messages
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "schema": schema, "strict": True},
                },
                max_completion_tokens=self._max_completion_tokens,
                reasoning_effort=self._reasoning_effort,
            )
        except APIConnectionError as exc:
            raise AiProviderUnavailableError("Microsoft Foundry este inaccesibil.") from exc
        except APIError as exc:
            raise AiProviderError("Microsoft Foundry a raspuns cu o eroare.") from exc

        usage = response.usage
        cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        continut = response.choices[0].message.content or ""

        try:
            date = json.loads(continut)
        except json.JSONDecodeError as exc:
            # Nu ar trebui sa se intample cu `strict: true`, dar reasoning_tokens
            # poate consuma tot bugetul si lasa raspunsul trunchiat — acelasi
            # gotcha ca la _EMPTY_ANSWER_FALLBACK_RO din orchestrator.py.
            logger.warning("foundry complete_json: JSON invalid din model: %r", continut[:200])
            raise AiProviderError("Modelul nu a raspuns cu JSON valid.") from exc

        return StructuredCompletion(
            data=date,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            tokens_cached=cached,
            deployment=self.deployment,
        )


class MicrosoftFoundryEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.foundry_configured:
            raise AiProviderUnavailableError("Microsoft Foundry nu este configurat.")

        self.deployment = settings.foundry_embedding_deployment
        self._client = AsyncOpenAI(base_url=settings.foundry_endpoint, api_key=settings.foundry_api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = await self._client.embeddings.create(model=self.deployment, input=texts)
        except APIConnectionError as exc:
            raise AiProviderUnavailableError("Microsoft Foundry este inaccesibil.") from exc
        except APIError as exc:
            raise AiProviderError("Microsoft Foundry a raspuns cu o eroare.") from exc

        return [item.embedding for item in response.data]

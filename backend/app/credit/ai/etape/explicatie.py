"""Etapa 'explicatie' — rescrie textul determinist pentru client, mai cald.

Singura etapa care ajunge la client (prin `credit_cereri.explicatie`, deja
afisat in aplicatie). Nu produce campuri structurate — text simplu — deci
foloseste `ChatProvider.complete()` obisnuit, nu `complete_json`.

Ruleaza SINCRON, in interiorul `evalueaza()` (vezi `_cu_explicatie` din
credit_service.py) — nu prin `CreditAiPipeline`, care e async si lazy: textul
trebuie sa fie deja pe cerere cand raspunde `POST /cereri/{id}/evalueaza`. De
aceea nu se scrie in `credit_ai_rulari`/`credit_ai_etape` (acelea modeleaza o
"rulare" de fundal), ci direct in `ai_usage_records`, cu acelasi tipar de cost
tracking ca restul aplicatiei (orchestrator.py `_record_telemetry`).
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.credit.ai.prompturi import SISTEM_EXPLICATIE, mesaj_utilizator_explicatie
from app.orchestration.output_guardrail import redact
from app.providers.base import ChatMessage, ChatProvider
from app.repositories.telemetry_repository import TelemetryRepository
from app.telemetry.metrics import estimate_chat_cost

logger = logging.getLogger(__name__)

# Un text rescris nu are voie sa fie mult mai scurt decat originalul — semn ca
# modelul a taiat un fapt in loc sa doar il reformuleze.
_LUNGIME_MINIMA_RELATIVA = 0.5

ExplicaCallback = Callable[[object, str], Awaitable[str | None]]


def fabrica_explica(
    provider: ChatProvider | None,
    *,
    telemetry: TelemetryRepository | None = None,
    environment: str = "local",
    price_per_million_in: float = 0.0,
    price_per_million_out: float = 0.0,
) -> ExplicaCallback | None:
    """Callback pentru `CreditService(explica=...)`, sau None cand Foundry nu e
    configurat — serviciul ramane pe deplin functional fara el (ARCHITECTURE.md #10)."""
    if provider is None:
        return None

    async def _explica(decizie: object, text_determinist: str) -> str | None:
        if not text_determinist.strip():
            return None

        mesaje = [
            ChatMessage(role="system", content=SISTEM_EXPLICATIE),
            ChatMessage(role="user", content=mesaj_utilizator_explicatie(text_determinist)),
        ]
        completare = await provider.complete(mesaje)

        if telemetry is not None:
            cost = estimate_chat_cost(
                completare.tokens_in, completare.tokens_out, price_per_million_in, price_per_million_out
            )
            try:
                await telemetry.record_usage(
                    feature="credit_pipeline", agent_id="explicatie", deployment=completare.deployment,
                    environment=environment, tokens_in=completare.tokens_in, tokens_out=completare.tokens_out,
                    tokens_cached=completare.tokens_cached, estimated_cost_usd=cost,
                )
            except Exception:
                logger.exception("nu am putut inregistra costul etapei explicatie")

        text = redact(completare.text.strip())
        if len(text) < len(text_determinist) * _LUNGIME_MINIMA_RELATIVA:
            logger.warning("explicatie AI suspect de scurta fata de originalul determinist; ignor")
            return None
        return text or None

    return _explica

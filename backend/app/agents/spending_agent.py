"""Agentul care raspunde la intrebari despre banii utilizatorului.

Rationeaza si alege tool-uri; nu vede schema bazei de date, nu scrie SQL si nu
poate modifica stare financiara (cap. 10 din ARCHITECTURE.md).
"""

import logging
from uuid import UUID

from anthropic import AsyncAnthropic

from app.infrastructure.config import Settings
from app.schemas.agents import ApelTool, ChatRequest, ChatResponse
from app.services.spending_service import SpendingService
from app.tools.financial_tools import construieste_tools

logger = logging.getLogger(__name__)

INSTRUCTIUNI = """Esti asistentul financiar al aplicatiei bancare Libra. Raspunzi in romana, scurt si direct.

Reguli:
- Orice cifra din raspuns vine dintr-un tool. Nu estima, nu inventa si nu completa din memorie.
- Daca tool-urile nu acopera intrebarea, spune clar ce nu poti afla.
- Ai acces doar la datele utilizatorului conectat. Daca ti se cere contul altcuiva, refuza.
- Nu poti face transferuri, nu poti bloca sau debloca un card si nu poti modifica nimic.
  Cand utilizatorul cere asa ceva, indica-i ecranul din aplicatie.
- Sumele se scriu cu doua zecimale si cu valuta (ex. 1.234,50 RON).
- Nu da sfaturi de investitii si nu promite randamente."""


class SpendingAgent:
    def __init__(
        self,
        client: AsyncAnthropic,
        settings: Settings,
        service: SpendingService,
        user_id: UUID,
    ) -> None:
        self._client = client
        self._settings = settings
        self._tools = construieste_tools(service, user_id)
        self._user_id = user_id

    async def raspunde(self, cerere: ChatRequest) -> ChatResponse:
        mesaje: list[dict] = [
            {"role": mesaj.rol, "content": mesaj.continut} for mesaj in cerere.istoric
        ]
        mesaje.append({"role": "user", "content": cerere.mesaj})

        runner = self._client.beta.messages.tool_runner(
            model=self._settings.agent_model,
            max_tokens=self._settings.agent_max_tokens,
            system=INSTRUCTIUNI,
            tools=self._tools,
            messages=mesaje,
            thinking={"type": "adaptive"},
            output_config={"effort": self._settings.agent_effort},
            # Bucla se opreste singura; plafonul e plasa de siguranta.
            max_iterations=self._settings.agent_max_pasi,
            # Daca un clasificator de siguranta refuza cererea, raspunsul e
            # rutat automat catre alt model in loc sa iasa gol.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

        apeluri: list[ApelTool] = []
        pasi = 0
        ultimul = None

        async for mesaj in runner:
            ultimul = mesaj
            pasi += 1
            for bloc in mesaj.content:
                if bloc.type == "tool_use":
                    apeluri.append(ApelTool(nume=bloc.name, argumente=dict(bloc.input)))

        if pasi >= self._settings.agent_max_pasi:
            logger.warning("agent oprit la plafonul de pasi user=%s pasi=%s", self._user_id, pasi)

        logger.info(
            "agent raspuns user=%s pasi=%s tool_uri=%s",
            self._user_id,
            pasi,
            [apel.nume for apel in apeluri],
        )

        return ChatResponse(raspuns=_text_final(ultimul), tool_uri_folosite=apeluri, pasi=pasi)


def _text_final(mesaj) -> str:
    if mesaj is None:
        return "Nu am putut genera un raspuns. Incearca din nou."

    if getattr(mesaj, "stop_reason", None) == "refusal":
        return "Nu pot raspunde la aceasta cerere."

    bucati = [bloc.text for bloc in mesaj.content if bloc.type == "text" and bloc.text.strip()]
    if not bucati:
        return "Nu am reusit sa duc la capat raspunsul. Reformuleaza intrebarea."
    return "\n\n".join(bucati).strip()

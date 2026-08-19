"""Tool-urile pe care le poate apela agentul.

Regula din ARCHITECTURE.md (cap. 7): agentul decide DE CE informatie are nevoie,
aplicatia decide DACA are voie si CUM se obtine. De aceea `user_id` nu este
parametru de tool — fiecare tool e o inchidere peste contextul autentificat, iar
modelul nu are cum sa ceara datele altui utilizator.
"""

import logging
from typing import Any, Callable
from uuid import UUID

from anthropic import beta_async_tool

from app.services.spending_service import SpendingService

logger = logging.getLogger(__name__)


def construieste_tools(service: SpendingService, user_id: UUID) -> list[Callable[..., Any]]:
    """Construieste setul de tool-uri legat de un singur utilizator."""

    @beta_async_tool
    async def obtine_sold() -> dict:
        """Soldul disponibil al utilizatorului, insumat pe cardurile neblocate.

        Se foloseste pentru intrebari de tipul "cati bani am", "ce sold am".
        """
        logger.info("tool obtine_sold user=%s", user_id)
        return (await service.sold_sumar(user_id)).model_dump()

    @beta_async_tool
    async def obtine_cashflow_lunar(luni: int = 3, valuta: str = "RON") -> dict:
        """Incasarile, cheltuielile si netul pe fiecare luna calendaristica.

        Args:
            luni: Cate luni in urma, inclusiv luna curenta. Intre 1 si 12.
            valuta: Codul valutei, 3 litere mari. Implicit RON.
        """
        logger.info("tool obtine_cashflow_lunar user=%s luni=%s", user_id, luni)
        return (await service.cashflow_lunar(user_id, luni, valuta)).model_dump()

    @beta_async_tool
    async def obtine_tranzactii_recente(zile: int = 30, limita: int = 10) -> list[dict]:
        """Ultimele tranzactii ale utilizatorului, cu data, suma si directia.

        Se foloseste doar cand raspunsul cere tranzactii individuale; pentru
        totaluri se prefera obtine_cashflow_lunar, care intoarce sume agregate.

        Args:
            zile: Cat de departe in trecut se cauta. Intre 1 si 180.
            limita: Cate tranzactii se intorc. Intre 1 si 25.
        """
        logger.info("tool obtine_tranzactii_recente user=%s zile=%s", user_id, zile)
        return await service.tranzactii_recente(user_id, zile, limita)

    return [obtine_sold, obtine_cashflow_lunar, obtine_tranzactii_recente]

"""Tool determinist peste cardurile reale — niciodata numarul complet sau CVV-ul.

CardRepository.CAMPURI (repositories/card_repository.py) nici macar nu citeste
acele coloane din DB, deci nu exista nicio cale prin care ar putea scapa de
aici mai departe catre un agent (GUARDRAILS.md #13).
"""

from __future__ import annotations

from uuid import UUID

from app.core.security import PERMISSION_CARDS_READ, Principal
from app.repositories.card_repository import CardRepository
from app.tools.base import RiskLevel, SideEffect, ToolDefinition


def build_card_tools(repository: CardRepository) -> list[ToolDefinition]:
    async def get_cards(principal: Principal, _args: dict) -> dict:
        cards = await repository.ale_utilizatorului(UUID(principal.user_id))
        return {
            "cards": [
                {
                    "id": card["id"],
                    "style": card.get("card_style"),
                    "expiry": card.get("data_expirare"),
                    "is_blocked": card.get("is_blocked"),
                }
                for card in cards
            ]
        }

    return [
        ToolDefinition(
            name="get_cards",
            description=(
                "Returneaza cardurile utilizatorului curent: stil, data expirarii, status blocat. "
                "Niciodata numarul complet sau CVV."
            ),
            callback=get_cards,
            allowed_agents=frozenset({"transaction_intelligence"}),
            required_permissions=frozenset({PERMISSION_CARDS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
    ]

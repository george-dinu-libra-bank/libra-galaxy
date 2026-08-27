"""Mesajele oficiale ale bancii catre client, ca tool pentru asistent.

Exista pentru un caz anume: unui om i se blocheaza contul, primeste notificarea
si vrea sa intrebe „de ce?". Fara tool-ul asta, asistentul nu are de unde sti —
`get_accounts` ii spune ca exista un cont blocat, dar nu si motivul scris de
analist. Raspunsul ar fi fost o generalitate politicoasa, exact cand omul are
nevoie de un fapt.

Se citeste doar ce a scris banca, niciodata insemnarile interne: `analize_cont`
contine observatii scrise intre colegi si nu se atinge de aici. Notificarea e
partea gandita sa ajunga la client, si atat.
"""

from __future__ import annotations

from app.core.security import PERMISSION_ACCOUNTS_READ, Principal
from app.repositories.notificare_repository import NotificareRepository
from app.tools.base import RiskLevel, SideEffect, ToolDefinition

# Cate mesaje se dau agentului. Destul cat sa acopere o blocare urmata de o
# deblocare, fara sa umple contextul cu istorie veche.
LIMITA = 5


def build_notificari_tools(repository: NotificareRepository) -> list[ToolDefinition]:
    async def get_bank_messages(principal: Principal, _args: dict) -> dict:
        mesaje = await repository.ale_utilizatorului(principal.user_id, LIMITA)
        return {
            "messages": [
                {
                    "title": m.get("titlu"),
                    "body": m.get("mesaj"),
                    "kind": m.get("tip"),
                    "created_at": m.get("creat_la"),
                    "read": m.get("citita_la") is not None,
                }
                for m in mesaje
            ]
        }

    return [
        ToolDefinition(
            name="get_bank_messages",
            description=(
                "Mesajele oficiale trimise de banca acestui client (blocare de cont, "
                "deblocare, atentionari), cele mai recente primele. Foloseste-l cand "
                "clientul intreaba de ce i s-a blocat contul sau ce i-a comunicat banca."
            ),
            callback=get_bank_messages,
            allowed_agents=frozenset({"transaction_intelligence", "compliance_kyc"}),
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
    ]

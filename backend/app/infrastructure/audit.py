"""Urma pe care o lasa agentii. Cap. 18 din ARCHITECTURE.md.

Se logheaza cine a cerut, ce capabilitate a fost apelata si cu ce argumente.
Nu se logheaza sume, descrieri de tranzactii sau alte date personale — pentru
depanare e suficient numele tool-ului si forma argumentelor.
"""

import logging
from uuid import UUID

logger = logging.getLogger("libra.agenti")

# Argumentele care se pot loga in clar; restul se reduc la tip.
ARGUMENTE_NESENSIBILE = frozenset({"luni", "zile", "limita", "valuta", "prag"})


def _curata(argumente: dict) -> dict:
    return {
        cheie: (valoare if cheie in ARGUMENTE_NESENSIBILE else f"<{type(valoare).__name__}>")
        for cheie, valoare in argumente.items()
    }


def apel_tool(user_id: UUID, agent: str, tool: str, argumente: dict) -> None:
    logger.info(
        "tool agent=%s tool=%s user=%s argumente=%s", agent, tool, user_id, _curata(argumente)
    )


def delegare(user_id: UUID, catre: str) -> None:
    logger.info("delegare catre=%s user=%s", catre, user_id)


def raspuns_agent(user_id: UUID, agent: str, pasi: int, tool_uri: list[str]) -> None:
    logger.info("raspuns agent=%s user=%s pasi=%s tool_uri=%s", agent, user_id, pasi, tool_uri)

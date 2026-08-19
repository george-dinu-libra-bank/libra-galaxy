"""Contractul comun al agentilor si bucla de tool use.

Un agent = instructiuni + un set de tool-uri + bucla de mai jos. Orchestratorul
nu stie nimic altceva despre ei, deci se pot adauga sau inlocui fara sa se atinga
restul aplicatiei.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.infrastructure import audit
from app.infrastructure.config import Settings
from app.infrastructure.llm import ClientModel, mesaj_asistent, mesaj_tool
from app.tools.unealta import Unealta

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RezultatAgent:
    agent: str
    raspuns: str
    tool_uri: list[str] = field(default_factory=list)
    pasi: int = 0
    disponibil: bool = True


class Agent(Protocol):
    nume: str
    descriere: str

    async def executa(self, sarcina: str) -> RezultatAgent: ...


class AgentIndisponibil:
    """Agent din diagrama care inca nu e implementat.

    Exista ca sa fie inregistrat de pe acum: modelul afla ce urmeaza sa existe si
    raspunde onest ca nu poate inca, in loc sa improvizeze.
    """

    def __init__(self, nume: str, descriere: str, motiv: str) -> None:
        self.nume = nume
        self.descriere = descriere
        self._motiv = motiv

    async def executa(self, sarcina: str) -> RezultatAgent:
        return RezultatAgent(agent=self.nume, raspuns=self._motiv, disponibil=False)


async def ruleaza_bucla(
    client: ClientModel,
    instructiuni: str,
    unelte: list[Unealta],
    mesaje: list[dict],
    max_pasi: int,
    user_id: UUID,
    nume_agent: str,
) -> tuple[str, list[str], int]:
    """Cere modelului un raspuns, executa tool-urile cerute, repeta.

    Se opreste cand modelul nu mai cere tool-uri sau cand se atinge plafonul.
    Intoarce textul final, tool-urile folosite si numarul de pasi.
    """
    dupa_nume = {unealta.nume: unealta for unealta in unelte}
    definitii = [unealta.definitie() for unealta in unelte]
    istoric = [{"role": "system", "content": instructiuni}, *mesaje]

    folosite: list[str] = []
    ultimul_text = ""
    # Modelele repeta acelasi apel cu aceleasi argumente in aceeasi tura. Nu e
    # ceva ce se rezolva sigur din prompt, deci raspunsul se refoloseste: datele
    # nu se schimba intre doi pasi, iar fiecare apel evitat inseamna o interogare
    # mai putin in baza si un raspuns mai rapid.
    deja_cerute: dict[tuple[str, str], object] = {}

    for pas in range(1, max_pasi + 1):
        raspuns = await client.completeaza(istoric, definitii)
        ultimul_text = raspuns.text or ultimul_text

        if not raspuns.cere_tool:
            return raspuns.text.strip(), folosite, pas

        istoric.append(mesaj_asistent(raspuns))

        for apel in raspuns.apeluri:
            folosite.append(apel.nume)
            audit.apel_tool(user_id, nume_agent, apel.nume, apel.argumente)

            cheie = (apel.nume, json.dumps(apel.argumente, sort_keys=True))
            if cheie in deja_cerute:
                logger.info("apel repetat, refolosesc raspunsul: %s", apel.nume)
                rezultat = deja_cerute[cheie]
            else:
                rezultat = await _executa(dupa_nume, apel)
                deja_cerute[cheie] = rezultat

            istoric.append(mesaj_tool(apel, rezultat))

    logger.warning("agent=%s a atins plafonul de %s pasi user=%s", nume_agent, max_pasi, user_id)
    return (
        ultimul_text.strip() or "Nu am reusit sa duc raspunsul la capat.",
        folosite,
        max_pasi,
    )


async def _executa(dupa_nume: dict[str, Unealta], apel) -> object:
    unealta = dupa_nume.get(apel.nume)
    if unealta is None:
        # Modelul a inventat un tool. Ii spunem, ca sa se corecteze in pasul urmator.
        return {"eroare": f"Tool-ul '{apel.nume}' nu exista."}
    try:
        return await unealta.executa(**apel.argumente)
    except TypeError as eroare:
        return {"eroare": f"Argumente gresite: {eroare}"}
    except Exception:
        logger.exception("tool %s a esuat", apel.nume)
        return {"eroare": "Tool-ul a esuat. Nu relua apelul identic."}


class AgentModel:
    """Agent care isi ruleaza propria bucla peste propriile tool-uri."""

    def __init__(
        self,
        nume: str,
        descriere: str,
        instructiuni: str,
        unelte: list[Unealta],
        client: ClientModel,
        settings: Settings,
        user_id: UUID,
    ) -> None:
        self.nume = nume
        self.descriere = descriere
        self._instructiuni = instructiuni
        self._unelte = unelte
        self._client = client
        self._settings = settings
        self._user_id = user_id

    async def executa(self, sarcina: str) -> RezultatAgent:
        text, folosite, pasi = await ruleaza_bucla(
            client=self._client,
            instructiuni=self._instructiuni,
            unelte=self._unelte,
            mesaje=[{"role": "user", "content": sarcina}],
            max_pasi=self._settings.agent_max_pasi,
            user_id=self._user_id,
            nume_agent=self.nume,
        )
        audit.raspuns_agent(self._user_id, self.nume, pasi, folosite)
        return RezultatAgent(agent=self.nume, raspuns=text, tool_uri=folosite, pasi=pasi)

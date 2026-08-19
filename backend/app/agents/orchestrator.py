"""Orchestratorul din diagrama.

Nu raspunde el la intrebari despre bani: alege specialistul, ii da sarcina si
compune raspunsul final. Fiecare specialist e expus ca tool de delegare, asa ca o
intrebare mixta ("cat am cheltuit si blocheaza-mi cardul") poate ajunge la mai
multi agenti in aceeasi tura — lucru pe care un router cu clasificator nu il face.

Orchestratorul nu vede tool-urile de date ale specialistilor, doar rezultatul lor.
Asa contextul ramane mic si granitele de securitate raman per agent.
"""

from uuid import UUID

from app.agents.baza import Agent, RezultatAgent, ruleaza_bucla
from app.infrastructure import audit
from app.infrastructure.config import Settings
from app.infrastructure.llm import ClientModel
from app.schemas.agents import ApelAgent, ChatRequest, ChatResponse
from app.tools.unealta import Unealta

INSTRUCTIUNI = """Esti orchestratorul asistentului bancar Libra. Raspunzi in romana.

Nu raspunzi tu la intrebari despre banii utilizatorului. Alegi agentul potrivit, ii dai o
sarcina clara si formulezi raspunsul final pe baza a ce iti intoarce el.

Reguli:
- Nu inventa cifre si nu completa un raspuns partial cu presupuneri.
- O intrebare poate cere mai multi agenti. Cheama-i pe toti cei necesari inainte sa raspunzi.
- Daca un agent spune ca nu e disponibil, transmite asta simplu si spune ce poate face
  utilizatorul intre timp. Nu pretinde ca s-a executat ceva.
- Daca intrebarea nu tine de banca, raspunde scurt ca nu e treaba ta.
- Nu repeta mecanic ce a zis agentul: da raspunsul direct, scurt, la obiect.
- NU pune intrebari de clarificare pentru lucruri pe care agentul le poate afla cu valori
  implicite rezonabile. "Cat am cheltuit pe luni" inseamna ultimele luni, in RON: deleaga
  direct. Ceri lamuriri doar cand fara ele raspunsul ar fi gresit, nu doar mai putin precis."""


def _unealta_de_delegare(agent: Agent, user_id: UUID, jurnal: list[ApelAgent]) -> Unealta:
    """Impacheteaza un agent intr-un tool pe care orchestratorul il poate chema."""

    async def deleaga(sarcina: str) -> dict:
        audit.delegare(user_id, agent.nume)
        rezultat: RezultatAgent = await agent.executa(sarcina)
        jurnal.append(
            ApelAgent(
                agent=rezultat.agent,
                disponibil=rezultat.disponibil,
                tool_uri=rezultat.tool_uri,
            )
        )
        return {
            "agent": rezultat.agent,
            "raspuns": rezultat.raspuns,
            "disponibil": rezultat.disponibil,
        }

    return Unealta(
        nume=f"deleaga_{agent.nume}",
        descriere=(
            f"{agent.descriere} Agentul nu vede conversatia, deci pune in sarcina tot "
            "contextul de care are nevoie."
        ),
        executa=deleaga,
        proprietati={
            "sarcina": {
                "type": "string",
                "description": "Ce trebuie sa afle sau sa faca agentul, formulat complet.",
            }
        },
        obligatorii=["sarcina"],
    )


class Orchestrator:
    def __init__(
        self,
        client: ClientModel,
        settings: Settings,
        agenti: list[Agent],
        user_id: UUID,
    ) -> None:
        self._client = client
        self._settings = settings
        self._agenti = agenti
        self._user_id = user_id

    async def raspunde(self, cerere: ChatRequest) -> ChatResponse:
        jurnal: list[ApelAgent] = []
        unelte = [_unealta_de_delegare(agent, self._user_id, jurnal) for agent in self._agenti]

        mesaje = [{"role": m.rol, "content": m.continut} for m in cerere.istoric]
        mesaje.append({"role": "user", "content": cerere.mesaj})

        text, _, pasi = await ruleaza_bucla(
            client=self._client,
            instructiuni=INSTRUCTIUNI,
            unelte=unelte,
            mesaje=mesaje,
            max_pasi=self._settings.agent_max_pasi,
            user_id=self._user_id,
            nume_agent="orchestrator",
        )

        audit.raspuns_agent(self._user_id, "orchestrator", pasi, [a.agent for a in jurnal])
        return ChatResponse(raspuns=text, agenti=jurnal, pasi=pasi)

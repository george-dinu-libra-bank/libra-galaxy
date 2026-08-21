"""Agent Actiuni — executa operatiuni cerute de utilizator.

Nu e implementat inca, si nu din lene: cap. 10 din ARCHITECTURE.md cere ca orice
mutare de bani sa treaca printr-un serviciu cu validare de sold, limite,
idempotenta, tranzactie atomica si eveniment de audit. `TransferService` nu
exista. Pana atunci agentul refuza explicit, ca sa nu para ca a facut ceva.

Cand se implementeaza: agentul PROPUNE actiunea si intoarce o recapitulare;
executia ramane in serviciu, dupa confirmare explicita in interfata.
"""

from app.agents.baza import AgentIndisponibil

NUME = "actiuni"
DESCRIERE = (
    "Executa operatiuni: transfer de bani, blocarea sau deblocarea unui card, "
    "plati programate. Momentan indisponibil."
)
MOTIV = (
    "Executia operatiunilor nu e disponibila prin asistent. Transferurile se fac din ecranul "
    "Transfer, iar blocarea unui card din ecranul Carduri."
)


def construieste() -> AgentIndisponibil:
    return AgentIndisponibil(NUME, DESCRIERE, MOTIV)

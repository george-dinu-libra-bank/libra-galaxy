"""Agent RAG Q&A — raspunde despre produsele si regulile bancii.

Nu e implementat inca: are nevoie de o baza de cunostinte (comisioane, termeni,
limite) si de o cautare peste ea. Deciziile deschise sunt pgvector cu embeddings
versus cautare full-text in Postgres.
"""

from app.agents.baza import AgentIndisponibil

NUME = "intrebari_banca"
DESCRIERE = (
    "Raspunde la intrebari despre banca: comisioane, limite, produse, termeni si "
    "conditii, cum functioneaza un serviciu. Momentan indisponibil."
)
MOTIV = (
    "Nu am inca baza de cunostinte a bancii, asa ca nu pot raspunde la intrebari despre "
    "comisioane, limite sau conditii."
)


def construieste() -> AgentIndisponibil:
    return AgentIndisponibil(NUME, DESCRIERE, MOTIV)

"""Agent Cititor Doc/Bon — extrage date dintr-un bon sau o factura.

Nu e implementat inca: are nevoie de o cale de incarcare a fisierului (Supabase
Storage) si de citirea lui cu Claude ca document, cu output structurat.
"""

from app.agents.baza import AgentIndisponibil

NUME = "documente"
DESCRIERE = (
    "Citeste bonuri, facturi si documente incarcate de utilizator si extrage "
    "sumele, comerciantul si data. Momentan indisponibil."
)
MOTIV = "Citirea bonurilor si a facturilor nu e disponibila inca."


def construieste() -> AgentIndisponibil:
    return AgentIndisponibil(NUME, DESCRIERE, MOTIV)

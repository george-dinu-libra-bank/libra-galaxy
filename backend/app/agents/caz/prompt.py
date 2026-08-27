"""Instructiunile comune celor trei agenti de investigatie.

Deliberat NU se foloseste `build_system_prompt` din app/agents/base.py. Acela e
scris pentru asistentul clientului si contine reguli care aici ar fi gresite:
interzice salutul (orchestratorul asistentului il adauga separat, dar o scrisoare
a bancii chiar incepe cu „Buna ziua"), cere raspuns in limba intrebarii (aici nu
exista o intrebare a utilizatorului), si vorbeste despre tool-uri si citari, pe
care agentii de aici nu le au. Refolosirea lui ar fi insemnat sa combat jumatate
din el cu exceptii.
"""

from app.agents.base import AgentSpec


def instructiuni(spec: AgentSpec, reguli: str = "") -> str:
    """Prompt de sistem pornind de la specificatia declarata a agentului.

    Interdictiile vin din `spec.prohibited`, nu din textul de aici: asa raman
    intr-un singur loc, langa scopul agentului, si se pot citi fara sa deschizi
    implementarea.
    """
    responsabilitati = "\n".join(f"- {item}" for item in spec.responsibilities)
    interdictii = "\n".join(f"- NU {item}" for item in spec.prohibited)

    parti = [
        f"Esti agentul '{spec.agent_id}' din Galaxy Bank. Scop: {spec.purpose}",
        "",
        "Ce ai de facut:",
        responsabilitati,
        "",
        "Ce nu ai voie sa faci, in nicio formulare si sub nicio forma:",
        interdictii,
        "",
        # Cazul poate ajunge intr-o contestatie, unde clientul are dreptul sa
        # vada ce s-a scris despre el. Un text care suna a acuzatie, scris de un
        # model care n-a vazut niciodata omul, e o problema juridica, nu doar una
        # de ton.
        "Scrii in limba romana, cu diacritice, in propozitii legate. Nimic din ce "
        "scrii nu presupune ca s-a stabilit ceva: sistemul a semnalat niste plati, "
        "atat. Orice afirmatie a ta trebuie sa se sprijine pe faptele primite mai jos.",
    ]

    if reguli:
        parti.extend(["", reguli.strip()])

    return "\n".join(parti)

"""Ce vad agentii dintr-un caz.

Un singur loc unde se decide ce iese din baza de date catre model. Agentii nu
primesc randuri brute: primesc structura de aici, si atat. Doua motive.

Primul e de confidentialitate. Un rand din `tranzactii` are id-uri, IBAN-ul
contului, IP-ul de la care s-a platit. Nimic din toate astea nu ajuta un model
sa scrie o intrebare limpede catre un om, iar ce nu ajuta nu se trimite. IP-ul
in special: e semnalul care a deschis cazul, dar e un semnal slab — un client cu
VPN arata identic cu unul spart — si scris intr-un mesaj ar suna ca o acuzatie
sprijinita pe o dovada care nu e dovada.

Al doilea e ca modelul sa nu poata inventa. Redactorul nu are de unde sa scoata
o suma care nu e in lista de mai jos, pentru ca nu vede nimic altceva.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class TranzactieCaz:
    """O plata semnalata, in forma in care poate fi citita cu voce tare."""

    data: date
    suma: float
    valuta: str
    comerciant: str
    motiv: str

    def rand(self) -> str:
        return (
            f"{self.data.strftime('%d.%m.%Y')} — {self.suma:.2f} {self.valuta} "
            f"la {self.comerciant} ({self.motiv})"
        )


@dataclass(frozen=True, slots=True)
class FapteCaz:
    """Cazul, asa cum il vede un agent.

    `prenume_client` e doar prenumele, nu numele intreg: mesajul incepe cu
    „Buna ziua, Andrei", nu cu numele complet dintr-un dosar.
    """

    prenume_client: str
    motiv_deschidere: str
    gravitate: int | None
    numar_semnalari: int | None
    tranzactii: tuple[TranzactieCaz, ...] = ()
    intrebari: tuple[str, ...] = ()
    cont_blocat: bool = False
    note_administrator: str = ""

    def rezumat(self) -> str:
        """Faptele, ca text pentru prompt.

        Scrise ca proza si liste scurte, nu ca JSON. Modelele urmeaza mai bine
        instructiunile cand contextul arata a text citit de om, iar aici nu e
        nimic de parsat inapoi — iesirea redactorului si a analistului e proza.
        """
        randuri = [f"Prenumele clientului: {self.prenume_client or 'necunoscut'}"]
        randuri.append(f"De ce s-a deschis cazul: {self.motiv_deschidere}")

        if self.gravitate is not None:
            randuri.append(
                f"Gravitatea calculata de sistemul de detectie: {self.gravitate} din 100"
            )
        if self.numar_semnalari is not None:
            randuri.append(f"Numar de plati semnalate: {self.numar_semnalari}")

        randuri.append(
            "Contul clientului este blocat in acest moment."
            if self.cont_blocat
            else "Contul clientului NU este blocat."
        )

        if self.tranzactii:
            randuri.append("\nPlatile semnalate:")
            randuri.extend(f"  - {t.rand()}" for t in self.tranzactii)

        if self.note_administrator.strip():
            randuri.append(f"\nObservatia administratorului: {self.note_administrator.strip()}")

        if self.intrebari:
            randuri.append("\nIntrebarile la care banca vrea raspuns:")
            randuri.extend(f"  {i}. {intrebare}" for i, intrebare in enumerate(self.intrebari, 1))

        return "\n".join(randuri)


@dataclass(frozen=True, slots=True)
class RaspunsExtras:
    """Un raspuns al clientului la o intrebare, adus in forma comparabila."""

    intrebare: str
    valoare: str  # "da" | "nu" | "nu_a_spus"
    citat: str = ""

    def rand(self) -> str:
        eticheta = {"da": "DA", "nu": "NU", "nu_a_spus": "nu a raspuns"}.get(
            self.valoare, self.valoare
        )
        if self.citat:
            return f"  - {self.intrebare} → {eticheta} („{self.citat}”)"
        return f"  - {self.intrebare} → {eticheta}"


@dataclass(frozen=True, slots=True)
class RaspunsClient:
    """Ce a trimis clientul: textul lui, plus citirea structurata a extractorului."""

    text: str
    campuri: tuple[RaspunsExtras, ...] = field(default=())

    def rezumat(self) -> str:
        randuri = [f"Ce a scris clientul, cuvant cu cuvant:\n„{self.text.strip()}”"]
        if self.campuri:
            randuri.append("\nCitirea structurata a raspunsului:")
            randuri.extend(c.rand() for c in self.campuri)
        return "\n".join(randuri)

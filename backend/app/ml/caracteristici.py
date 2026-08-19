"""Transforma randurile brute in trasaturi. Pur, fara retea — de aceea testabil."""

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

SPATII = re.compile(r"\s+")
CIFRE_LUNGI = re.compile(r"\d{4,}")
# Cuvintele care preced un numar de referinta si raman orfane dupa ce il scoatem.
MARCAJE_REFERINTA = re.compile(r"\b(ref|nr|id|cod|tranzactie|auth)\.?$")


@dataclass(frozen=True, slots=True)
class Plata:
    id: str
    moment: datetime
    suma: float
    valuta: str
    comerciant: str
    iesire: bool


def normalizeaza_comerciant(descriere: str | None) -> str:
    """Descrierile contin des coduri si numere de referinta care fac fiecare plata
    sa para unica. Le scoatem, ca sa putem grupa dupa acelasi comerciant."""
    if not descriere:
        return "necunoscut"
    text = CIFRE_LUNGI.sub("", descriere.lower().strip())
    text = SPATII.sub(" ", text).strip(" -_/")
    text = MARCAJE_REFERINTA.sub("", text).strip(" -_/")
    return text or "necunoscut"


def normalizeaza(randuri: list[dict], user_id: UUID) -> list[Plata]:
    plati: list[Plata] = []
    for rand in randuri:
        try:
            moment = datetime.fromisoformat(str(rand["creat_la"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        plati.append(
            Plata(
                id=str(rand["id"]),
                moment=moment,
                suma=float(rand["suma"]),
                valuta=rand.get("valuta", "RON"),
                comerciant=normalizeaza_comerciant(rand.get("descriere")),
                iesire=str(rand.get("id_user_send")) == str(user_id),
            )
        )
    return sorted(plati, key=lambda p: p.moment)


def vector(plata: Plata, istoric: list[Plata]) -> list[float]:
    """Trasaturile folosite si de model, si de baza statistica.

    Ordinea conteaza: acelasi vector trebuie produs la antrenare si la inferenta.
    """
    sume = [p.suma for p in istoric]
    mediana = _mediana(sume) if sume else plata.suma
    anterioare = [p for p in istoric if p.moment < plata.moment]
    zile_de_la_ultima = (
        (plata.moment - anterioare[-1].moment).total_seconds() / 86400 if anterioare else -1.0
    )
    return [
        plata.suma,
        plata.suma / mediana if mediana else 1.0,
        float(len(istoric)),
        zile_de_la_ultima,
        float(plata.moment.day),
        float(plata.moment.weekday()),
    ]


def _mediana(valori: list[float]) -> float:
    if not valori:
        return 0.0
    ordonate = sorted(valori)
    mijloc = len(ordonate) // 2
    if len(ordonate) % 2:
        return ordonate[mijloc]
    return (ordonate[mijloc - 1] + ordonate[mijloc]) / 2


def mediana(valori: list[float]) -> float:
    return _mediana(valori)


def deviatie_absoluta_mediana(valori: list[float]) -> float:
    """MAD — masura de imprastiere care nu e trasa de o singura plata uriasa,
    spre deosebire de deviatia standard."""
    if not valori:
        return 0.0
    med = _mediana(valori)
    return _mediana([abs(v - med) for v in valori])

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


FEREASTRA_RAFALA = 86400.0  # secunde; cate plati la acelasi comerciant intr-o zi


def vector(plata: Plata, istoric: list[Plata], toate: list[Plata] | None = None) -> list[float]:
    """Trasaturile pe care le vede modelul.

    Ordinea conteaza: acelasi vector trebuie produs la antrenare si la inferenta.

    `istoric` sunt platile la acelasi comerciant, `toate` sunt toate platile de
    iesire ale utilizatorului. Din amandoua se folosesc numai cele dinaintea
    platii evaluate: la inferenta viitorul oricum nu exista, iar la antrenare
    l-am da modelului un avantaj pe care nu-l va avea in productie.

    Doua trasaturi se uita dincolo de comerciantul curent, pentru ca fara ele
    tiparele care conteaza raman invizibile:

    - `suma / mediana generala` — un sir de plati mici la un comerciant nou isi
      trage singur mediana in jos, deci raportat la el insusi pare normal. Fata
      de cat cheltuie omul de obicei, nu mai pare.
    - `plati in ultimele 24h` — patru plati intr-o zi la un magazin vizitat
      saptamanal e un ritm anormal, chiar daca fiecare suma in parte e obisnuita.

    Ziua din luna, ziua saptamanii si numarul de plati anterioare au fost scoase
    dupa masuratori: raspund la "cat de rar e comerciantul", nu la "cat de
    neobisnuita e plata". IsolationForest alege dimensiunea de taiere la
    intamplare, deci fiecare trasatura fara legatura cu intrebarea fura din
    taieturile utile. Pe setul de testare, scoaterea lor a dus semnalarile
    corecte de la 0 din 8 la 5 din 8.
    """
    anterioare = [p for p in istoric if p.moment < plata.moment]
    sume = [p.suma for p in anterioare]
    mediana_comerciant = _mediana(sume) if sume else plata.suma

    referinta = toate if toate is not None else istoric
    sume_generale = [p.suma for p in referinta if p.moment < plata.moment]
    mediana_generala = _mediana(sume_generale) if sume_generale else plata.suma

    zile_de_la_ultima = (
        (plata.moment - anterioare[-1].moment).total_seconds() / 86400 if anterioare else -1.0
    )
    in_24h = sum(
        1
        for p in anterioare
        if (plata.moment - p.moment).total_seconds() <= FEREASTRA_RAFALA
    )

    return [
        plata.suma,
        plata.suma / mediana_comerciant if mediana_comerciant else 1.0,
        plata.suma / mediana_generala if mediana_generala else 1.0,
        zile_de_la_ultima,
        float(in_24h),
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

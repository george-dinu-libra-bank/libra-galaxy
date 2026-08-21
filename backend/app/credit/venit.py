"""Venitul dedus din incasarile reale ale utilizatorului.

Neavand acces la ANAF, asta e cea mai onesta sursa de venit pe care o are banca:
nu ce declara omul, ci ce i-a intrat efectiv in cont. Un salariu arata
caracteristic — aceeasi suma, de la acelasi platitor, la aproximativ 30 de zile.
Trei semnale trebuie sa apara simultan; oricare singur da fals-pozitive:

- **acelasi platitor**, altfel adunam transferuri fara legatura intre ele;
- **ritm lunar**, altfel un sir de plati de la un prieten ar trece drept salariu;
- **sume apropiate**, altfel niste transferuri intamplatoare de la aceeasi
  persoana ar parea venit.

Modulul e pur: primeste `Plata`-uri deja normalizate de `app/ml/caracteristici.py`
si nu atinge nici reteaua, nici baza de date.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ml.caracteristici import Plata, deviatie_absoluta_mediana, mediana

# Sub trei incasari nu se poate vorbi de ritm: doua puncte definesc un singur
# interval, iar un singur interval poate fi coincidenta.
MIN_INCASARI = 3
# Cat de departe de 30 de zile poate fi intervalul median si sa ramana "lunar".
# Salariile cad in zile lucratoare, deci un interval real oscileaza cu cateva
# zile in jurul lunii calendaristice.
INTERVAL_LUNAR_MIN = 25.0
INTERVAL_LUNAR_MAX = 35.0
# MAD / mediana. Peste atat, sumele sunt prea imprastiate ca sa fie un salariu:
# 0.15 lasa loc de bonusuri si de luni cu zile lucratoare diferite.
PRAG_DEVIATIE = 0.15
# De la atatea luni de istoric increderea nu mai creste: 12 luni de venituri e si
# cerinta produsului (galaxy-bank-knowledge/credite/eligibilitate.md).
LUNI_PENTRU_INCREDERE_MAXIMA = 12


@dataclass(frozen=True, slots=True)
class VenitConstatat:
    """Ce a gasit banca in tranzactii, cu masura cat de sigura e.

    `incredere` nu e o probabilitate calibrata, ci un scor 0-1 folosit ca sa
    departajeze sursele: un venit constatat cu incredere mica nu bate o
    adeverinta, unul cu incredere mare bate declaratia clientului.
    """

    venit_lunar: float
    luni_detectate: int
    platitor: str
    deviatie_relativa: float
    incredere: float


def detecteaza_venit(plati: list[Plata]) -> VenitConstatat | None:
    """Cel mai credibil venit recurent din incasari, sau None daca nu exista.

    Cand mai multi platitori trec testele (salariu plus o chirie incasata, de
    exemplu), castiga cel cu produsul incredere x suma cel mai mare: intre doua
    surse la fel de regulate conteaza care duce greul, iar intre doua surse egale
    ca suma conteaza care e mai regulata.
    """
    incasari = [plata for plata in plati if not plata.iesire]
    if not incasari:
        return None

    grupuri: dict[str, list[Plata]] = {}
    for plata in incasari:
        grupuri.setdefault(plata.comerciant, []).append(plata)

    candidati = [
        constatare
        for platitor, ale_lui in grupuri.items()
        if (constatare := _evalueaza_platitor(platitor, ale_lui)) is not None
    ]
    if not candidati:
        return None

    return max(candidati, key=lambda c: c.incredere * c.venit_lunar)


def _evalueaza_platitor(platitor: str, plati: list[Plata]) -> VenitConstatat | None:
    if len(plati) < MIN_INCASARI:
        return None

    ordonate = sorted(plati, key=lambda p: p.moment)
    intervale = [
        (urmatoarea.moment - curenta.moment).total_seconds() / 86400
        for curenta, urmatoarea in zip(ordonate, ordonate[1:])
    ]

    interval_median = mediana(intervale)
    if not INTERVAL_LUNAR_MIN <= interval_median <= INTERVAL_LUNAR_MAX:
        return None

    sume = [plata.suma for plata in ordonate]
    suma_mediana = mediana(sume)
    if suma_mediana <= 0:
        return None

    deviatie_relativa = deviatie_absoluta_mediana(sume) / suma_mediana
    if deviatie_relativa > PRAG_DEVIATIE:
        return None

    return VenitConstatat(
        venit_lunar=round(suma_mediana, 2),
        luni_detectate=len(ordonate),
        platitor=platitor,
        deviatie_relativa=round(deviatie_relativa, 4),
        incredere=_incredere(len(ordonate), intervale, deviatie_relativa),
    )


def _incredere(numar_incasari: int, intervale: list[float], deviatie_relativa: float) -> float:
    """Trei componente, ponderate dupa cat de mult spun despre "e salariu".

    Istoricul cantareste cel mai mult: doua incasari perfect egale la 30 de zile
    raman doua incasari, in timp ce douasprezece incasari usor variabile sunt un
    tipar. Regularitatea intervalului si stabilitatea sumei confirma tiparul, dar
    nu il pot inlocui.
    """
    componenta_istoric = min(numar_incasari / LUNI_PENTRU_INCREDERE_MAXIMA, 1.0)

    # Cat de strans stau intervalele in jurul medianei lor, raportat la fereastra
    # acceptata. Un sir la exact 30, 30, 30 de zile da 1.0.
    imprastiere = deviatie_absoluta_mediana(intervale)
    componenta_ritm = max(0.0, 1.0 - imprastiere / (INTERVAL_LUNAR_MAX - INTERVAL_LUNAR_MIN))

    componenta_stabilitate = max(0.0, 1.0 - deviatie_relativa / PRAG_DEVIATIE)

    scor = 0.5 * componenta_istoric + 0.25 * componenta_ritm + 0.25 * componenta_stabilitate
    return round(min(scor, 1.0), 3)

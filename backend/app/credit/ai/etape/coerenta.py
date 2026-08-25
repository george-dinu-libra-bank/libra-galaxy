"""Etapa 'coerenta' — coroboreaza sursele intre ele, fara niciun model.

Pur, ca reguli.py: primeste date deja citite de service/repository si intoarce
`list[Semnal]`. Testabil cu cazuri construite, fara mock-uri de retea, si
disponibil chiar cand Foundry e cazut — ceea ce conteaza aici sunt comparatii
de numere, un hash si o distanta intre siruri.

Pragurile sunt constante la varf, cu comentariu de calibrare — tiparul din
scorecard.py.
"""

from __future__ import annotations

import re
from decimal import Decimal
from difflib import SequenceMatcher

from app.credit.ai.contracte import ExtractieDocument, Semnal
from app.credit.venit import VenitConstatat
from app.ml.caracteristici import Plata, deviatie_absoluta_mediana, mediana

# Cat de mult poate depasi venitul declarat ceea ce arata incasarile reale
# inainte sa merite un semnal. Sub asta sunt diferente normale (bonus lunar
# variabil, ore suplimentare); peste, cineva a scris o cifra optimista.
PRAG_VENIT_DECLARAT_UMFLAT = Decimal("1.3")

# Similaritate Ratcliff/Obershelp intre numele angajatorului declarat si
# platitorul real din tranzactii, dupa normalizare. Sub prag, numele n-au
# nicio legatura vizibila.
PRAG_SIMILARITATE_ANGAJATOR = 0.5

# Cat de mult poate diferi venitul citit din document fata de cel din
# tranzactii inainte sa merite atentie. Peste asta, cel putin una dintre cele
# doua surse e gresita.
PRAG_DIFERENTA_DOCUMENT_TRANZACTII = Decimal("0.2")

# Fereastra in care o incasare mare, chiar inainte de cerere, e suspecta de
# "pregatire" a dosarului.
ZILE_INCASARI_PREGATITOARE = 30
# Acelasi prag robust (MAD) ca in ml/neregularitati.py — o incasare la peste
# 3.5 deviatii absolute mediane fata de restul e statistic neobisnuita.
PRAG_SCOR_INCASARE_PREGATITOARE = 3.5
# O incasare sub asta nu merita semnalata, oricat de atipica ar fi statistic.
SUMA_MINIMA_INCASARE_PREGATITOARE = Decimal("500")
# Cand istoricul e perfect regulat (aceeasi suma de fiecare data — MAD zero),
# nu orice abatere conteaza: o incasare cu 5% mai mare e normala. Trebuie sa
# fie vizibil mai mare decat tiparul, nu doar diferita de el.
MULTIPLU_MINIM_ISTORIC_REGULAT = Decimal("1.5")

# Cat de aproape de pragul de calificare (venit.py: PRAG_DEVIATIE = 0.15) poate
# fi deviatia unui venit deja constatat inainte sa merite un semnal informativ.
# Sub asta, tiparul e limpede; intre asta si prag, e un salariu cu variatii
# mari de la o luna la alta.
PRAG_INFORMATIV_VENIT_NEREGULAT = Decimal("0.08")

_SUFIXE_FIRMA = re.compile(r"\b(s\.?\s?r\.?\s?l\.?|s\.?\s?a\.?|s\.?\s?c\.?|pfa|i\.?i\.?)\b", re.IGNORECASE)
_NECARACTERE = re.compile(r"[^a-z0-9\s]")
_SPATII = re.compile(r"\s+")


def _normalizeaza_nume(text: str) -> str:
    text = _SUFIXE_FIRMA.sub(" ", text.lower())
    text = _NECARACTERE.sub(" ", text)
    return _SPATII.sub(" ", text).strip()


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalizeaza_nume(a), _normalizeaza_nume(b)).ratio()


def evalueaza(
    *,
    cerere: dict,
    documente: list[dict],
    documente_reutilizate: list[dict],
    venit_constatat: VenitConstatat | None,
    plati: list[Plata],
    extractie_document: ExtractieDocument | None = None,
) -> list[Semnal]:
    """Toate semnalele de coerenta pentru o cerere, intr-o singura trecere.

    `documente_reutilizate` = randuri din credit_documente cu acelasi
    `hash_fisier` ca unul dintre `documente`, apartinand altei cereri sau altui
    utilizator — gasite de repository (index credit_documente_hash_idx),
    trecute aici deja calculate: functia ramane pura.
    """
    semnale: list[Semnal] = []

    semnal = _document_reutilizat(documente_reutilizate)
    if semnal:
        semnale.append(semnal)

    semnal = _venit_declarat_umflat(cerere, venit_constatat)
    if semnal:
        semnale.append(semnal)

    semnal = _angajator_nepotrivit(cerere, venit_constatat)
    if semnal:
        semnale.append(semnal)

    semnal = _document_vs_tranzactii(documente, extractie_document, venit_constatat)
    if semnal:
        semnale.append(semnal)

    semnale.extend(_incasari_pregatitoare(cerere, plati))

    semnal = _venit_neregulat(venit_constatat)
    if semnal:
        semnale.append(semnal)

    semnale.extend(_documente_ilizibile(documente))

    return semnale


def _document_reutilizat(documente_reutilizate: list[dict]) -> Semnal | None:
    if not documente_reutilizate:
        return None
    alte_cereri = sorted({str(d["id_cerere"]) for d in documente_reutilizate})
    return Semnal(
        cod="document_reutilizat",
        severitate="grav",
        titlu="Acelasi fisier a mai fost incarcat la alta cerere.",
        detaliu={"alte_cereri": alte_cereri},
    )


def _venit_declarat_umflat(cerere: dict, venit_constatat: VenitConstatat | None) -> Semnal | None:
    if venit_constatat is None:
        return None
    declarat = Decimal(str(cerere.get("venit_declarat") or 0))
    constatat = Decimal(str(venit_constatat.venit_lunar))
    if declarat <= 0 or constatat <= 0:
        return None
    if declarat <= constatat * PRAG_VENIT_DECLARAT_UMFLAT:
        return None
    return Semnal(
        cod="venit_declarat_umflat",
        severitate="atentie",
        titlu="Venitul declarat e mult peste ce arata incasarile din cont.",
        detaliu={"declarat": str(declarat), "constatat_din_tranzactii": str(constatat)},
    )


def _angajator_nepotrivit(cerere: dict, venit_constatat: VenitConstatat | None) -> Semnal | None:
    angajator = (cerere.get("angajator") or "").strip()
    if not angajator or venit_constatat is None or not venit_constatat.platitor:
        return None
    similaritate = _similar(angajator, venit_constatat.platitor)
    if similaritate >= PRAG_SIMILARITATE_ANGAJATOR:
        return None
    return Semnal(
        cod="angajator_nepotrivit",
        severitate="atentie",
        titlu="Angajatorul declarat nu seamana cu platitorul incasarilor recurente.",
        detaliu={
            "angajator_declarat": angajator,
            "platitor_din_tranzactii": venit_constatat.platitor,
            "similaritate": round(similaritate, 2),
        },
    )


def _venit_document(
    documente: list[dict], extractie_document: ExtractieDocument | None
) -> Decimal | None:
    """Cea mai buna cifra disponibila din document: extractia AI daca a rulat,
    altfel ce a citit deja regex-ul la incarcare (`extras.venit_net`)."""
    if extractie_document is not None and extractie_document.venit_net is not None:
        return extractie_document.venit_net
    for document in documente:
        venit = (document.get("extras") or {}).get("venit_net")
        if venit is not None:
            try:
                return Decimal(str(venit))
            except Exception:
                continue
    return None


def _document_vs_tranzactii(
    documente: list[dict], extractie_document: ExtractieDocument | None, venit_constatat: VenitConstatat | None
) -> Semnal | None:
    if venit_constatat is None:
        return None
    din_document = _venit_document(documente, extractie_document)
    if din_document is None or din_document <= 0:
        return None
    din_tranzactii = Decimal(str(venit_constatat.venit_lunar))
    if din_tranzactii <= 0:
        return None
    diferenta = abs(din_document - din_tranzactii) / din_tranzactii
    if diferenta <= PRAG_DIFERENTA_DOCUMENT_TRANZACTII:
        return None
    return Semnal(
        cod="document_vs_tranzactii",
        severitate="atentie",
        titlu="Venitul din adeverinta difera semnificativ de incasarile din cont.",
        detaliu={
            "din_document": str(din_document),
            "din_tranzactii": str(din_tranzactii),
            "diferenta_procentuala": round(float(diferenta) * 100, 1),
        },
    )


def _incasari_pregatitoare(cerere: dict, plati: list[Plata]) -> list[Semnal]:
    creat_la = cerere.get("creat_la")
    if not creat_la:
        return []
    try:
        from datetime import datetime, timedelta

        moment_cerere = datetime.fromisoformat(str(creat_la).replace("Z", "+00:00"))
    except ValueError:
        return []

    fereastra_start = moment_cerere - timedelta(days=ZILE_INCASARI_PREGATITOARE)
    incasari = [p for p in plati if not p.iesire]
    recente = [p for p in incasari if fereastra_start <= p.moment < moment_cerere]
    istoric = [p for p in incasari if p.moment < fereastra_start]

    if not recente or len(istoric) < 3:
        return []

    sume_istoric = [p.suma for p in istoric]
    med = mediana(sume_istoric)
    imprastiere = deviatie_absoluta_mediana(sume_istoric)

    semnale: list[Semnal] = []
    for plata in recente:
        if plata.suma < float(SUMA_MINIMA_INCASARE_PREGATITOARE) or plata.suma <= med:
            continue
        if imprastiere == 0:
            # Istoric perfect regulat (aceeasi suma de fiecare data): o abatere
            # mica e normala (rotunjiri, cativa lei in plus), dar de la un
            # multiplu vizibil in sus tiparul chiar s-a rupt.
            if plata.suma < med * float(MULTIPLU_MINIM_ISTORIC_REGULAT):
                continue
            scor = PRAG_SCOR_INCASARE_PREGATITOARE
        else:
            scor = 0.6745 * abs(plata.suma - med) / imprastiere
        if scor < PRAG_SCOR_INCASARE_PREGATITOARE:
            continue
        semnale.append(Semnal(
            cod="incasari_pregatitoare",
            severitate="atentie",
            titlu="Incasare neobisnuit de mare, chiar inainte de depunerea cererii.",
            detaliu={
                "suma": round(plata.suma, 2), "data": plata.moment.date().isoformat(),
                "de_la": plata.comerciant, "median_istoric": round(med, 2),
            },
        ))
    return semnale


def _venit_neregulat(venit_constatat: VenitConstatat | None) -> Semnal | None:
    if venit_constatat is None:
        return None
    deviatie = Decimal(str(venit_constatat.deviatie_relativa))
    if deviatie < PRAG_INFORMATIV_VENIT_NEREGULAT:
        return None
    return Semnal(
        cod="venit_neregulat",
        severitate="informativ",
        titlu="Incasarile recurente variaza destul de mult de la o luna la alta.",
        detaliu={"deviatie_relativa": round(float(deviatie), 3)},
    )


def _documente_ilizibile(documente: list[dict]) -> list[Semnal]:
    return [
        Semnal(
            cod="document_ilizibil",
            severitate="informativ",
            titlu="Un document incarcat n-a putut fi citit automat.",
            detaliu={"id_document": str(document["id"])},
        )
        for document in documente
        if document.get("status") == "ilizibil"
    ]

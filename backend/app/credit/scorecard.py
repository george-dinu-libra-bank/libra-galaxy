"""Punctajul de bonitate — nuanta de dupa criteriile hard.

`reguli.py` raspunde binar: cine nu trece de el nu ajunge aici. Modulul asta
raspunde la ce spune documentatia explicit ca ramane de decis dupa aceea —
„criteriile minime nu sunt suficiente pentru aprobare; banca verifica veniturile,
obligatiile existente, istoricul relevant, gradul de indatorare si alte criterii
de risc" (galaxy-bank-knowledge/credite/eligibilitate.md).

Doua principii, amandoua deliberate:

1. **Fiecare factor isi spune punctajul si motivul.** Un scor de 63 fara
   explicatie nu poate fi contestat de client si nici aparat de banca. Aici,
   63 vine cu „gradul de indatorare 34% — 8 din 30 de puncte".
2. **Niciun model de limbaj nu intra in calcul.** Scorul e o functie pura de
   numere, deci se poate reproduce peste un an, pe aceleasi date, cu acelasi
   rezultat. Modelul doar formuleaza in cuvinte ce s-a decis aici.

Zona gri nu e un esec al modelului, ci proiectata: intre 45 si 69 decizia merge
la un om, fiindca acolo stau dosarele unde cifrele singure nu ajung.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.credit.reguli import PRAG_DTI

PRAG_APROBARE = 70
PRAG_ANALIZA_MANUALA = 45

DECIZIE_APROBAT = "aprobat"
DECIZIE_ANALIZA_MANUALA = "analiza_manuala"
DECIZIE_RESPINS = "respins"

# Punctele maxime per factor. Suma e 100 — verificata in teste, ca sa nu se
# strecoare o modificare care schimba scara fara sa schimbe pragurile.
PUNCTE_DTI = 30
PUNCTE_MARJA_VENIT = 20
PUNCTE_VECHIME = 15
PUNCTE_DOVADA_VENIT = 15
PUNCTE_RELATIE = 10
PUNCTE_COMPORTAMENT = 10

# Punctele de saturatie sunt calibrate pe cum arata un dosar bun in realitate,
# nu pe un ideal teoretic. Prima varianta cerea 36 de luni de vechime si un venit
# de 3x minimul ca sa dea punctaj plin, si un solicitant solid — 6.200 RON net,
# DTI 20%, 18 luni la angajator, venit confirmat din incasari — ieseau 59 de
# puncte, adica analiza manuala. Un asemenea dosar trebuie sa se aprobe singur;
# altfel zona gri se umple de cazuri care n-au ce cauta acolo si oamenii ajung
# sa aprobe manual ce ar fi trebuit sa treaca automat.

# Doi ani la acelasi angajator inseamna stabilitate; peste, nu mai adauga nimic.
VECHIME_SATURATIE_LUNI = 24
# Un venit de doua ori si jumatate peste minim e tot ce se poate cere rezonabil.
MARJA_VENIT_SATURATIE = Decimal("2.5")
RELATIE_SATURATIE_LUNI = 18
# De la atatea plati atipice in ultimele luni, factorul de comportament e zero.
NEREGULARITATI_SATURATIE = 4
# Sub acest grad de indatorare omul are spatiu real de manevra, deci punctaj
# plin. Intre el si plafonul de 40% punctajul scade liniar.
DTI_CONFORTABIL = Decimal("0.15")


@dataclass(frozen=True, slots=True)
class Factor:
    cod: str
    puncte: int
    maxim: int
    explicatie: str


@dataclass(frozen=True, slots=True)
class DateScoring:
    """Tot ce intra in punctaj, deja adunat de serviciu din surse diferite."""

    dti: Decimal
    venit_net: Decimal
    venit_minim_produs: Decimal
    vechime_angajator_luni: int
    # Cat de bine e dovedit venitul: 1.0 = dedus din incasari recurente stabile,
    # ~0.6 = adeverinta, 0.0 = doar declarat. Vine din sursa care a castigat.
    incredere_venit: float
    luni_de_la_deschiderea_contului: int
    # Cate plati atipice a gasit DetectorNeregularitati in istoricul recent.
    neregularitati_recente: int


@dataclass(frozen=True, slots=True)
class Scor:
    total: int
    decizie: str
    factori: list[Factor]

    @property
    def aprobat(self) -> bool:
        return self.decizie == DECIZIE_APROBAT


def calculeaza(date: DateScoring) -> Scor:
    factori = [
        _factor_dti(date),
        _factor_marja_venit(date),
        _factor_vechime(date),
        _factor_dovada_venit(date),
        _factor_relatie(date),
        _factor_comportament(date),
    ]
    total = sum(factor.puncte for factor in factori)
    return Scor(total=total, decizie=decizie_pentru(total), factori=factori)


def decizie_pentru(total: int) -> str:
    if total >= PRAG_APROBARE:
        return DECIZIE_APROBAT
    if total >= PRAG_ANALIZA_MANUALA:
        return DECIZIE_ANALIZA_MANUALA
    return DECIZIE_RESPINS


def _factor_dti(date: DateScoring) -> Factor:
    """Cel mai greu factor: masoara direct daca omul poate plati rata.

    Sub 15% da tot punctajul, plafonul de 40% da zero. Cine e peste plafon nici
    nu ajunge aici — l-a oprit `reguli.py`.
    """
    puncte = _interpolare(date.dti, PRAG_DTI, DTI_CONFORTABIL, PUNCTE_DTI)
    return Factor(
        "dti", puncte, PUNCTE_DTI,
        f"Grad de indatorare {date.dti:.1%} din plafonul de {PRAG_DTI:.0%}.",
    )


def _factor_marja_venit(date: DateScoring) -> Factor:
    """Cat spatiu de respiratie ramane peste pragul minim al produsului.

    Doi oameni cu acelasi DTI nu sunt la fel de siguri daca unul castiga 3.100
    si celalalt 15.000: la o cheltuiala neprevazuta, primul nu mai are din ce.
    """
    marja = date.venit_net / date.venit_minim_produs if date.venit_minim_produs > 0 else Decimal(1)
    puncte = _interpolare(marja, Decimal(1), MARJA_VENIT_SATURATIE, PUNCTE_MARJA_VENIT)
    return Factor(
        "marja_venit", puncte, PUNCTE_MARJA_VENIT,
        f"Venit de {marja:.1f} ori peste minimul produsului.",
    )


def _factor_vechime(date: DateScoring) -> Factor:
    puncte = _interpolare(
        Decimal(date.vechime_angajator_luni), Decimal(0), Decimal(VECHIME_SATURATIE_LUNI), PUNCTE_VECHIME
    )
    return Factor(
        "vechime_angajator", puncte, PUNCTE_VECHIME,
        f"{date.vechime_angajator_luni} luni la angajatorul actual.",
    )


def _factor_dovada_venit(date: DateScoring) -> Factor:
    """Cat de mult se sprijina cifra pe fapte, nu pe declaratii.

    Fara ANAF, asta e diferenta dintre un venit pe care banca l-a vazut intrand
    in cont si unul pe care l-a auzit de la client.
    """
    incredere = min(max(date.incredere_venit, 0.0), 1.0)
    puncte = round(incredere * PUNCTE_DOVADA_VENIT)
    return Factor(
        "dovada_venit", puncte, PUNCTE_DOVADA_VENIT,
        f"Venit confirmat in proportie de {incredere:.0%} din surse verificabile.",
    )


def _factor_relatie(date: DateScoring) -> Factor:
    puncte = _interpolare(
        Decimal(date.luni_de_la_deschiderea_contului), Decimal(0), Decimal(RELATIE_SATURATIE_LUNI), PUNCTE_RELATIE
    )
    return Factor(
        "relatie_banca", puncte, PUNCTE_RELATIE,
        f"{date.luni_de_la_deschiderea_contului} luni de cand e client Galaxy Bank.",
    )


def _factor_comportament(date: DateScoring) -> Factor:
    """Platile atipice gasite de detectorul de neregularitati.

    Nu e o judecata morala: un istoric cu multe plati care ies din tipar e mai
    greu de prezis, iar creditarea e in esenta o predictie.
    """
    puncte = _interpolare(
        Decimal(date.neregularitati_recente), Decimal(NEREGULARITATI_SATURATIE), Decimal(0), PUNCTE_COMPORTAMENT
    )
    return Factor(
        "comportament", puncte, PUNCTE_COMPORTAMENT,
        f"{date.neregularitati_recente} plati atipice in istoricul recent.",
    )


def _interpolare(valoare: Decimal, capat_zero: Decimal, capat_maxim: Decimal, puncte: int) -> int:
    """Puncte intre 0 si `puncte`, liniar intre cele doua capete, cu taiere.

    Merge in ambele sensuri: daca `capat_maxim < capat_zero`, factorul scade cand
    valoarea creste (cazul DTI si al neregularitatilor).
    """
    if capat_maxim == capat_zero:
        return puncte

    fractie = (valoare - capat_zero) / (capat_maxim - capat_zero)
    fractie = min(max(fractie, Decimal(0)), Decimal(1))
    return int((fractie * puncte).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

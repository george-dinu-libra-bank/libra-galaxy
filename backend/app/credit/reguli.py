"""Criteriile hard de eligibilitate — ce respinge o cerere fara discutie.

Sursa nu e inventata aici: galaxy-bank-knowledge/credite/eligibilitate.md si
credit-nevoi-personale.md. Pragurile concrete stau in `credit_produse`, deci
modulul primeste produsul ca parametru si nu are constante de produs in cod.

Singura constanta care nu vine din produs e plafonul gradului de indatorare:
40% pentru credite de consum, pragul din normele BNR. E o regula de banca, nu de
produs, si se aplica peste orice ar zice catalogul.

Separatia fata de `scorecard.py`: aici sunt raspunsurile binare ("are 19 ani, nu
se poate"), acolo e nuanta ("are venit bun, dar istoric scurt"). Documentatia o
spune explicit — indeplinirea criteriilor minime nu garanteaza aprobarea.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PRAG_DTI = Decimal("0.40")

# Prima cifra din CNP da secolul nasterii. 7 si 8 sunt rezidenti straini, pentru
# care regula de secol nu e fixata prin lege — se decide dupa plauzibilitate.
SECOL_DUPA_CIFRA = {1: 1900, 2: 1900, 3: 1800, 4: 1800, 5: 2000, 6: 2000}
VARSTA_IMPLAUZIBILA = 120


@dataclass(frozen=True, slots=True)
class Motiv:
    """Un motiv de respingere. Codul e pentru masini, textul pentru oameni.

    Textul ajunge in fata clientului ca atare cand nu e disponibil un model de
    limbaj, deci e scris sa fie citit, nu sa fie parsat — si e singurul loc din
    backend scris CU diacritice. Restul codului le evita, dar un mesaj de banca
    afisat pe jumatate cu si pe jumatate fara arata neingrijit.
    """

    cod: str
    text: str


@dataclass(frozen=True, slots=True)
class Produs:
    """Oglinda unui rand din `credit_produse`."""

    slug: str
    nume: str
    dobanda_anuala: Decimal
    suma_min: Decimal
    suma_max: Decimal
    luni_min: int
    luni_max: int
    varsta_min: int
    varsta_max: int
    venit_net_minim: Decimal
    vechime_angajator_luni: int
    vechime_venituri_luni: int


@dataclass(frozen=True, slots=True)
class Solicitant:
    """Ce stie banca despre cel care cere creditul, dupa verificari."""

    cnp: str
    verification_status: str
    venit_net: Decimal
    obligatii_lunare: Decimal
    vechime_angajator_luni: int
    vechime_venituri_luni: int


def varsta_din_cnp(cnp: str, la_data: date | None = None) -> int:
    """Varsta derivata din CNP, nu declarata de client.

    CNP-ul e validat la inregistrare si inghetat de trigger pe profil, deci e cea
    mai de incredere data pe care o are banca despre cine e omul.

    Format: S AA LL ZZ ..., unde S da secolul.
    """
    cnp = cnp.strip()
    if len(cnp) != 13 or not cnp.isdigit():
        raise ValueError("CNP invalid: trebuie sa aiba exact 13 cifre.")

    cifra, an_scurt = int(cnp[0]), int(cnp[1:3])
    luna, zi = int(cnp[3:5]), int(cnp[5:7])
    la_data = la_data or date.today()

    if cifra in SECOL_DUPA_CIFRA:
        an = SECOL_DUPA_CIFRA[cifra] + an_scurt
    elif cifra in (7, 8):
        # Rezident strain: incercam intai secolul XX, iar daca ar da o varsta
        # imposibila, secolul XXI.
        an = 1900 + an_scurt
        if la_data.year - an > VARSTA_IMPLAUZIBILA:
            an = 2000 + an_scurt
    else:
        raise ValueError(f"CNP invalid: prima cifra {cifra} nu indica un secol.")

    try:
        nastere = date(an, luna, zi)
    except ValueError as eroare:
        raise ValueError("CNP invalid: data nasterii nu exista.") from eroare

    # Scaderea anilor minus o zi daca ziua de nastere nu a trecut inca anul asta.
    implinita = (la_data.month, la_data.day) >= (nastere.month, nastere.day)
    return la_data.year - nastere.year - (0 if implinita else 1)


def grad_indatorare(
    venit_net: Decimal, obligatii_lunare: Decimal, rata_noua: Decimal
) -> Decimal:
    """(obligatii existente + rata noua) / venit net.

    Rata noua intra in numarator: intrebarea nu e daca omul isi permite ce are
    acum, ci daca isi permite si creditul asta.
    """
    if venit_net <= 0:
        raise ValueError("Venitul net trebuie sa fie pozitiv.")
    return ((obligatii_lunare + rata_noua) / venit_net).quantize(Decimal("0.0001"))


def verifica(
    produs: Produs,
    solicitant: Solicitant,
    suma: Decimal,
    luni: int,
    rata_lunara: Decimal,
    la_data: date | None = None,
) -> list[Motiv]:
    """Toate motivele de respingere, nu doar primul.

    Se aduna toate dinadins: un client care afla pe rand ca nu are varsta, apoi
    ca nu are venitul, apoi ca nu are vechimea, ar reveni de trei ori degeaba.
    Lista goala inseamna ca trece de criteriile hard — nu ca e aprobat.
    """
    motive: list[Motiv] = []

    if suma < produs.suma_min or suma > produs.suma_max:
        motive.append(Motiv(
            "suma_in_afara_limitelor",
            f"{produs.nume} se acordă între {produs.suma_min:,.0f} și {produs.suma_max:,.0f} RON.",
        ))

    if luni < produs.luni_min or luni > produs.luni_max:
        motive.append(Motiv(
            "perioada_in_afara_limitelor",
            f"Perioada trebuie să fie între {produs.luni_min} și {produs.luni_max} de luni.",
        ))

    try:
        varsta = varsta_din_cnp(solicitant.cnp, la_data)
    except ValueError:
        motive.append(Motiv("cnp_invalid", "Nu am putut determina vârsta din CNP."))
    else:
        if varsta < produs.varsta_min or varsta > produs.varsta_max:
            motive.append(Motiv(
                "varsta_neeligibila",
                f"{produs.nume} se acordă între {produs.varsta_min} și {produs.varsta_max} de ani.",
            ))

    if solicitant.venit_net < produs.venit_net_minim:
        motive.append(Motiv(
            "venit_sub_minim",
            f"Venitul net minim pentru {produs.nume} este {produs.venit_net_minim:,.0f} RON pe lună.",
        ))

    if solicitant.vechime_angajator_luni < produs.vechime_angajator_luni:
        motive.append(Motiv(
            "vechime_angajator_insuficienta",
            f"Sunt necesare minimum {produs.vechime_angajator_luni} luni la angajatorul actual.",
        ))

    if solicitant.vechime_venituri_luni < produs.vechime_venituri_luni:
        motive.append(Motiv(
            "vechime_venituri_insuficienta",
            f"Sunt necesare minimum {produs.vechime_venituri_luni} luni de venituri eligibile.",
        ))

    # Verificarea de identitate existenta (OCR buletin + comparare faciala,
    # migrarea 0007) devine poarta de creditare: banca nu imprumuta bani cuiva pe
    # care nu l-a identificat.
    if solicitant.verification_status != "verified":
        motive.append(Motiv(
            "identitate_neverificata",
            "Identitatea contului trebuie verificată înainte de acordarea unui credit.",
        ))

    if solicitant.venit_net > 0:
        dti = grad_indatorare(solicitant.venit_net, solicitant.obligatii_lunare, rata_lunara)
        if dti > PRAG_DTI:
            motive.append(Motiv(
                "grad_indatorare_depasit",
                f"Gradul de îndatorare ar ajunge la {dti:.1%}, peste plafonul de {PRAG_DTI:.0%}.",
            ))

    return motive

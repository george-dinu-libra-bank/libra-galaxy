"""Amortizarea cu anuitate constanta: rata, graficul, DAE, rambursarea anticipata.

Pur, fara retea si fara baza de date — de aceea testabil, ca `app/ml/caracteristici.py`.

Doua decizii se vad in toate semnaturile de aici:

1. **Banii sunt intregi, in bani (1 RON = 100 bani), niciodata float.** Un grafic
   pe 60 de luni inseamna 120 de rotunjiri succesive; in float erorile se aduna
   si soldul final nu mai cade pe zero, ci pe 0.004 sau -0.007 RON. Pe hartie e
   nimic, in contabilitate e un credit care nu se poate inchide.
2. **Ultima rata absoarbe restul.** Rata lunara e aceeasi in toate lunile, dar
   dobanda si principalul din interiorul ei se rotunjesc fiecare la ban.
   Diferenta adunata nu se imparte si nu se ignora: ultima rata stinge exact cat
   a mai ramas, deci suma principalelor e fix creditul acordat.

Ratele de dobanda circula ca `Decimal` (0.099 pentru 9,90% pe an). Se accepta si
float sau str la intrare, convertite prin `str()` ca sa nu intre in calcul
artefactele binare ale lui float — `Decimal(0.099)` e 0.09900000000000000199...,
`Decimal(str(0.099))` e exact 0.099.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

BANI_IN_LEU = 100
LUNI_IN_AN = 12
# Dobanda intre doua scadente se socoteste pe zile efective (conventia ACT/365):
# la o rambursare la mijlocul lunii, clientul nu datoreaza luna intreaga.
ZILE_IN_AN = 365

# Cautarea DAE se opreste cand intervalul scade sub atat, pe rata lunara. La 1e-9
# lunar, eroarea anuala e sub o miime de punct procentual — invizibila dupa
# rotunjirea la doua zecimale cu care se afiseaza oricum.
PRAG_CAUTARE_DAE = Decimal("0.000000001")
MAX_ITERATII_DAE = 400
# Capatul de sus al cautarii: 100% pe luna. Orice credit real e mult sub.
RATA_LUNARA_MAXIMA = Decimal(1)


@dataclass(frozen=True, slots=True)
class RataProgramata:
    """O linie din graficul de rambursare.

    `total_bani` nu e mereu egal cu rata lunara: la ultima rata difera cu restul
    din rotunjiri, absorbit acolo.
    """

    numar: int
    principal_bani: int
    dobanda_bani: int
    total_bani: int
    sold_dupa_bani: int


@dataclass(frozen=True, slots=True)
class CostRambursare:
    """Cat are de platit clientul ca sa stinga creditul azi.

    `galaxy-bank-knowledge/credite/rambursare-anticipata.md` spune explicit ca
    documentatia nu defineste un comision de rambursare anticipata si ca agentul
    nu are voie sa inventeze unul. De aceea aici nu exista camp de comision: se
    raporteaza soldul si dobanda acumulata de la ultima scadenta, atat.
    """

    sold_bani: int
    dobanda_acumulata_bani: int
    total_bani: int
    economie_dobanda_bani: int


def bani_din_lei(lei: Decimal | float | str) -> int:
    """Converteste un numeric(14,2) din baza de date in bani intregi."""
    return _rotunjeste(_zecimal(lei) * BANI_IN_LEU)


def lei_din_bani(bani: int) -> Decimal:
    """Converteste inapoi, pentru scriere in numeric(14,2) sau pentru afisare."""
    return (Decimal(bani) / BANI_IN_LEU).quantize(Decimal("0.01"))


def rata_lunara_bani(principal_bani: int, dobanda_anuala: Decimal | float | str, luni: int) -> int:
    """Anuitatea constanta: R = P·i·(1+i)^n / ((1+i)^n − 1), cu i = dobanda/12.

    Se foloseste forma cu exponent pozitiv, nu `P·i / (1 − (1+i)^−n)`: sunt
    echivalente algebric, dar a doua cere o impartire in plus, deci inca o
    rotunjire in Decimal.
    """
    _valideaza(principal_bani, luni)
    lunara = _zecimal(dobanda_anuala) / LUNI_IN_AN

    if lunara == 0:
        return _rotunjeste(Decimal(principal_bani) / luni)

    factor = (1 + lunara) ** luni
    return _rotunjeste(Decimal(principal_bani) * lunara * factor / (factor - 1))


def genereaza_grafic(
    principal_bani: int, dobanda_anuala: Decimal | float | str, luni: int
) -> list[RataProgramata]:
    """Graficul complet, garantat sa se inchida exact pe zero.

    Invariantii verificati in `tests/test_amortizare.py`:
      - `sold_dupa_bani` al ultimei rate e 0;
      - suma principalelor e exact `principal_bani`;
      - suma dobanzilor e exact `sum(total_bani) − principal_bani`.
    """
    _valideaza(principal_bani, luni)
    rata = rata_lunara_bani(principal_bani, dobanda_anuala, luni)
    lunara = _zecimal(dobanda_anuala) / LUNI_IN_AN

    grafic: list[RataProgramata] = []
    sold = principal_bani

    for numar in range(1, luni + 1):
        dobanda = _rotunjeste(Decimal(sold) * lunara)

        if numar == luni:
            # Ultima rata stinge tot ce a ramas, oricat s-a adunat din rotunjiri.
            principal = sold
            total = principal + dobanda
        else:
            principal = rata - dobanda
            total = rata
            if principal <= 0:
                # Rata nu acopera nici macar dobanda lunii, deci soldul ar creste
                # la nesfarsit. Cu anuitatea calculata mai sus nu se poate
                # intampla; daca se intampla, cineva a construit graficul de mana
                # cu parametri imposibili si e mai bine sa afle acum decat sa
                # primeasca un grafic care nu converge.
                raise ValueError(
                    f"Rata de {rata} bani nu acopera dobanda de {dobanda} bani la luna {numar}."
                )

        sold -= principal
        grafic.append(
            RataProgramata(
                numar=numar,
                principal_bani=principal,
                dobanda_bani=dobanda,
                total_bani=total,
                sold_dupa_bani=sold,
            )
        )

    return grafic


def dae(
    principal_bani: int,
    rata_bani: int,
    luni: int,
    comisioane_bani: int = 0,
) -> Decimal:
    """Dobanda anuala efectiva, ca fractie (0.103618 pentru 10,36%).

    E rata la care valoarea actualizata a ratelor egaleaza suma pe care clientul
    chiar o primeste in mana — principalul minus comisioanele retinute la
    acordare. Chiar fara comisioane, DAE iese peste dobanda nominala, din
    capitalizarea lunara: la 9,90% pe an, (1 + 0,099/12)^12 − 1 = 10,36%.

    Se rezolva prin bisectie, nu Newton-Raphson: functia e monoton descrescatoare
    in rata si avem de la inceput un interval care incadreaza radacina, deci
    bisectia converge garantat. Newton ar fi mai rapid, dar poate sari in afara
    intervalului cand derivata e mica, iar aici nu ne grabim.
    """
    _valideaza(principal_bani, luni)
    if rata_bani <= 0:
        raise ValueError("Rata lunara trebuie sa fie pozitiva.")

    incasat = principal_bani - comisioane_bani
    if incasat <= 0:
        raise ValueError("Comisioanele nu pot depasi principalul.")
    if rata_bani * luni <= incasat:
        # Clientul da inapoi mai putin decat a primit: nu exista o dobanda
        # pozitiva care sa satisfaca ecuatia.
        raise ValueError("Totalul ratelor nu depaseste suma incasata; DAE nu e definita.")

    jos, sus = Decimal(0), RATA_LUNARA_MAXIMA
    for _ in range(MAX_ITERATII_DAE):
        if sus - jos < PRAG_CAUTARE_DAE:
            break
        mijloc = (jos + sus) / 2
        # Valoarea actualizata scade cand rata creste: daca la mijloc inca
        # depaseste cat s-a incasat, radacina e mai sus.
        if _valoare_actualizata(rata_bani, luni, mijloc) > incasat:
            jos = mijloc
        else:
            sus = mijloc

    lunara = (jos + sus) / 2
    return ((1 + lunara) ** LUNI_IN_AN - 1).quantize(Decimal("0.000001"))


def sold_dupa(grafic: list[RataProgramata], rate_platite: int) -> int:
    """Soldul ramas dupa `rate_platite` rate achitate. Zero rate = principalul."""
    if not grafic:
        raise ValueError("Grafic gol.")
    if not 0 <= rate_platite <= len(grafic):
        raise ValueError(f"rate_platite trebuie sa fie intre 0 si {len(grafic)}.")

    if rate_platite == 0:
        # Principalul initial, reconstituit din prima linie.
        return grafic[0].sold_dupa_bani + grafic[0].principal_bani
    return grafic[rate_platite - 1].sold_dupa_bani


def cost_rambursare_anticipata(
    grafic: list[RataProgramata],
    rate_platite: int,
    zile_de_la_ultima_scadenta: int,
    dobanda_anuala: Decimal | float | str,
) -> CostRambursare:
    """Cat costa stingerea creditului azi si cata dobanda se economiseste.

    `economie_dobanda_bani` e diferenta dintre dobanda pe care clientul ar fi
    platit-o mergand pana la capat si cea datorata pana azi — cifra care il
    intereseaza cand decide daca merita.
    """
    if zile_de_la_ultima_scadenta < 0:
        raise ValueError("Numarul de zile nu poate fi negativ.")

    sold = sold_dupa(grafic, rate_platite)
    zilnica = _zecimal(dobanda_anuala) / ZILE_IN_AN
    acumulata = _rotunjeste(Decimal(sold) * zilnica * zile_de_la_ultima_scadenta)
    ramasa_programata = sum(rata.dobanda_bani for rata in grafic[rate_platite:])

    return CostRambursare(
        sold_bani=sold,
        dobanda_acumulata_bani=acumulata,
        total_bani=sold + acumulata,
        economie_dobanda_bani=ramasa_programata - acumulata,
    )


def _valoare_actualizata(rata_bani: int, luni: int, rata_lunara: Decimal) -> Decimal:
    """Valoarea de azi a `luni` rate egale, actualizate cu `rata_lunara`."""
    if rata_lunara == 0:
        return Decimal(rata_bani * luni)
    factor = (1 + rata_lunara) ** luni
    return Decimal(rata_bani) * (factor - 1) / (rata_lunara * factor)


def _valideaza(principal_bani: int, luni: int) -> None:
    if principal_bani <= 0:
        raise ValueError("Principalul trebuie sa fie pozitiv.")
    if luni <= 0:
        raise ValueError("Perioada trebuie sa fie de cel putin o luna.")


def _zecimal(valoare: Decimal | float | str) -> Decimal:
    return valoare if isinstance(valoare, Decimal) else Decimal(str(valoare))


def _rotunjeste(valoare: Decimal) -> int:
    """La ban, jumatatile in sus — conventia uzuala pentru sume de bani."""
    return int(valoare.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

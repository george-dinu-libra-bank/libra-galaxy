"""Citirea unei adeverinte de venit — text brut in cifre pe care le poate folosi banca.

Modulul primeste text (de la `pypdf` sau de la Tesseract) si nu atinge nici
reteaua, nici baza de date. La fel ca `venit.py` si `reguli.py`, se poate testa
in intregime fara sa existe un document adevarat.

**Alegerea care conteaza: cand nu stie, spune ca nu stie.** Parserul nu propune
niciodata o suma pe care n-o poate justifica printr-un cuvant-cheie din
document. O adeverinta are pe ea si brutul, si netul, si impozitul, si CAS-ul —
un numar ales fara sa stii ce eticheta are langa el nu e o citire, e un pariu.
Cand nu gaseste eticheta, intoarce `None`, iar analistul scrie cifra de mana.
Un camp gol e mai onest decat un camp completat gresit, si mai usor de observat.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Salariul net lunar plauzibil. Banda e larga dinadins: intrebarea de aici e
# "arata ca o suma de bani lunara?", nu "se califica pentru credit?" — a doua o
# pune reguli.py, cu pragul produsului. Un part-time de 900 lei trebuie citit
# corect chiar daca nu ia creditul.
VENIT_MINIM_PLAUZIBIL = Decimal(500)
VENIT_MAXIM_PLAUZIBIL = Decimal(200_000)

# Cuvintele de langa suma buna. Fara diacritice: textul e normalizat inainte,
# fiindca OCR-ul le pierde des si "plata" / "plată" trebuie sa se potriveasca
# amandoua. Ordinea conteaza — vezi _pozitie_cuvant_net.
CUVINTE_NET = (
    "net lunar", "salariu net", "salariul net", "venit net", "venitul net",
    "net de plata", "net incasat", "net realizat", "suma neta", "netul",
    "net",
)

# Cuvintele care descalifica o linie intreaga. Un numar de pe randul "salariu
# brut" nu e un candidat slab — e sigur gresit, si trebuie scos din discutie, nu
# punctat mai jos. Altfel, pe o adeverinta unde OCR-ul rateaza randul cu netul,
# brutul ar castiga prin lipsa de concurenta.
CUVINTE_INTERZISE = (
    "brut", "impozit", "retinut", "retineri", "cass", "sanatate",
    "somaj", "pensie", "deducere", "sindicat", "avans",
)

# Numarul romanesc: "4.850,00" · "4 850,00" · "4850,00" · "4.850" · "4850".
# Alternativa cu grupe de mii e prima, ca sa nu se opreasca dupa "4" din "4.850".
NUMAR = re.compile(r"\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?")

FORME_JURIDICE = re.compile(r"\b(s\.?c\.?|s\.?r\.?l\.?|s\.?a\.?|p\.?f\.?a\.?|srl)\b")
ETICHETE_ANGAJATOR = ("angajator", "societatea", "unitatea", "denumire", "subscrisa")

VECHIME = re.compile(r"vechime[^0-9]{0,40}?(\d{1,3})\s*(ani|an|luni|luna)")

# Cat de departe de cuvantul-cheie mai are sens sa fie suma, in caractere.
# "Salariul net lunar realizat in ultimele 6 luni este de 4.850,00 lei" are ~45.
DISTANTA_MAXIMA = 60


@dataclass(frozen=True, slots=True)
class DateAdeverinta:
    """Ce s-a putut citi. Orice camp poate lipsi — documentul e o poza, nu un API."""

    venit_net: Decimal | None
    angajator: str | None
    vechime_luni: int | None
    incredere: float
    text_brut: str

    @property
    def utilizabila(self) -> bool:
        return self.venit_net is not None


def _fara_diacritice(text: str) -> str:
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(caracter)
    )


def _linii(text: str) -> list[tuple[str, str]]:
    """Perechi (linie originala, linie normalizata), fara duplicate.

    Duplicatele apar fiindca `extrage_text` lipeste rezultatele mai multor
    preprocesari ale aceleiasi poze. Pastrarea lor ar face ca o linie citita de
    patru ori sa para de patru ori mai credibila decat una citita o data.
    """
    vazute: set[str] = set()
    perechi: list[tuple[str, str]] = []

    for linie in text.splitlines():
        original = " ".join(linie.split())
        if not original:
            continue
        normalizata = _fara_diacritice(original).lower()
        if normalizata in vazute:
            continue
        vazute.add(normalizata)
        perechi.append((original, normalizata))

    return perechi


def _numar(brut: str) -> Decimal | None:
    """Un numar romanesc in Decimal, sau None daca nu e o suma plauzibila.

    Punctul si virgula isi schimba rolurile fata de engleza, iar documentele
    amesteca ambele conventii. Regula care le desparte: **grupul de dupa ultimul
    separator**. Trei cifre inseamna separator de mii ("4.850" = 4850); una sau
    doua inseamna zecimale ("4850,00" = 4850.00). Banii romanesti n-au niciodata
    trei zecimale, deci ambiguitatea nu apare in practica.
    """
    curat = brut.replace(" ", "").replace(" ", "")

    if "," in curat and "." in curat:
        # Amandoua prezente: ultimul separator e cel zecimal.
        if curat.rindex(",") > curat.rindex("."):
            curat = curat.replace(".", "").replace(",", ".")
        else:
            curat = curat.replace(",", "")
    elif "," in curat:
        _, _, zecimale = curat.rpartition(",")
        curat = curat.replace(",", ".") if len(zecimale) <= 2 else curat.replace(",", "")
    elif "." in curat:
        _, _, zecimale = curat.rpartition(".")
        if len(zecimale) > 2:
            curat = curat.replace(".", "")

    try:
        valoare = Decimal(curat)
    except InvalidOperation:
        return None

    return valoare if VENIT_MINIM_PLAUZIBIL <= valoare <= VENIT_MAXIM_PLAUZIBIL else None


def _pozitie_cuvant_net(linie: str) -> int | None:
    """Sfarsitul celei mai specifice potriviri de "net" din linie.

    Se cauta in ordinea din CUVINTE_NET, de la specific la general, ca "salariu
    net" sa bata "net" simplu — altfel ancora ar cadea pe alt "net" din linie,
    iar distanta pana la suma ar fi masurata gresit.
    """
    for cuvant in CUVINTE_NET:
        pozitie = linie.find(cuvant)
        if pozitie != -1:
            return pozitie + len(cuvant)
    return None


def _interzisa(linie: str) -> bool:
    return any(cuvant in linie for cuvant in CUVINTE_INTERZISE)


def _sume_din_linie(linie: str) -> list[tuple[Decimal, int]]:
    sume = []
    for potrivire in NUMAR.finditer(linie):
        valoare = _numar(potrivire.group())
        if valoare is not None:
            sume.append((valoare, potrivire.start()))
    return sume


def _cauta_venit(linii: list[tuple[str, str]]) -> tuple[Decimal | None, float]:
    """Suma de langa cuvantul "net", si cat de sigur e ca e chiar ea.

    Doua forme, punctate diferit:

    - **pe aceeasi linie** ("Salariu net: 4.850,00 lei") — cazul obisnuit si cel
      mai sigur;
    - **pe linia urmatoare** — adeverintele in tabel au eticheta pe un rand si
      cifrele pe altul. Se puncteaza mai jos, fiindca legatura dintre coloana si
      eticheta e o presupunere, nu ceva citit.
    """
    candidati: list[tuple[float, Decimal]] = []

    for index, (_, linie) in enumerate(linii):
        if _interzisa(linie):
            continue

        dupa_cuvant = _pozitie_cuvant_net(linie)
        if dupa_cuvant is None:
            continue

        sume = [
            (valoare, pozitie - dupa_cuvant)
            for valoare, pozitie in _sume_din_linie(linie)
            if 0 <= pozitie - dupa_cuvant <= DISTANTA_MAXIMA
        ]
        if sume:
            valoare, distanta = min(sume, key=lambda pereche: pereche[1])
            # Cu cat suma e mai lipita de eticheta, cu atat e mai probabil ca
            # eticheta o descrie pe ea.
            candidati.append((0.9 - 0.2 * (distanta / DISTANTA_MAXIMA), valoare))
            continue

        # Forma de tabel: eticheta singura pe rand, cifrele pe randul de sub. Se
        # accepta numai daca randul urmator are exact o suma — cu doua sau mai
        # multe n-avem cum sti care coloana e a netului.
        urmatoarea = linii[index + 1][1] if index + 1 < len(linii) else ""
        if urmatoarea and not _interzisa(urmatoarea):
            sume_urmatoare = _sume_din_linie(urmatoarea)
            if len(sume_urmatoare) == 1:
                candidati.append((0.45, sume_urmatoare[0][0]))

    if not candidati:
        return None, 0.0

    scor, valoare = max(candidati, key=lambda pereche: pereche[0])

    # Doua citiri independente care cad pe aceeasi suma valoreaza mai mult decat
    # una singura: preprocesarile OCR difera, iar acordul dintre ele e semnal.
    if sum(1 for _, alta in candidati if alta == valoare) > 1:
        scor = min(1.0, scor + 0.1)

    return valoare, round(scor, 3)


def _cauta_angajator(linii: list[tuple[str, str]]) -> str | None:
    """Numele firmei, cautat intai dupa eticheta si abia apoi dupa forma juridica."""
    for index, (original, linie) in enumerate(linii):
        for eticheta in ETICHETE_ANGAJATOR:
            pozitie = linie.find(eticheta)
            if pozitie == -1:
                continue
            rest = original[pozitie + len(eticheta):].lstrip(" :.-")
            if rest:
                return rest[:120]
            # Eticheta singura pe rand: numele e pe randul urmator.
            if index + 1 < len(linii):
                return linii[index + 1][0][:120]

    for original, linie in linii:
        if FORME_JURIDICE.search(linie):
            return original[:120]

    return None


def _cauta_vechime(linii: list[tuple[str, str]]) -> int | None:
    for _, linie in linii:
        potrivire = VECHIME.search(linie)
        if not potrivire:
            continue
        cantitate, unitate = int(potrivire.group(1)), potrivire.group(2)
        luni = cantitate * 12 if unitate.startswith("an") else cantitate
        # Peste 60 de ani de vechime inseamna ca s-a citit gresit un numar.
        if 0 < luni <= 720:
            return luni
    return None


def citeste_adeverinta(text: str) -> DateAdeverinta:
    """Ce se poate afla dintr-o adeverinta de venit, fara sa se ghiceasca nimic.

    `incredere` se refera **numai la venit** — el e singurul camp care intra in
    decizia de creditare. Angajatorul si vechimea sunt informative: ajuta
    analistul sa recunoasca documentul, dar nu misca scorul.
    """
    linii = _linii(text)
    if not linii:
        return DateAdeverinta(None, None, None, 0.0, text)

    venit, incredere = _cauta_venit(linii)

    return DateAdeverinta(
        venit_net=venit,
        angajator=_cauta_angajator(linii),
        vechime_luni=_cauta_vechime(linii),
        incredere=incredere,
        text_brut=text,
    )

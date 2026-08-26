"""Gasirea unui CNP intr-un text citit de masina.

Functii pure: nici retea, nici Tesseract, nici Azure. Le folosesc amandoua
drumurile de OCR, si raman valabile si dupa ce Tesseract dispare din imagine.

Aici se opreste ambitia modulului: formatul brut, 13 cifre care incep cu 1-8.
Cifra de control se valideaza separat, la introducere (`validCnp` in frontend) —
un CNP citit de pe o poza trece pe sub ochii omului inainte sa insemne ceva.
"""

from __future__ import annotations

import re
from collections import Counter

# Prima cifra 1-8 (sex + secol), urmata de 12 cifre.
CNP_REGEX = re.compile(r"[1-8]\d{12}")

DOAR_CIFRE = re.compile(r"[^0-9]")

# Cate cuvinte alaturate se lipesc cand se cauta CNP-ul in lista de cuvinte.
# Trei ajung: "1970101 221144" (rupt in doua) sau "197 0101 221144"; peste atat
# nu mai e o rupere de OCR, ci alt numar de langa.
CUVINTE_LIPITE_MAXIM = 3


def candidati_din_text(text: str) -> list[str]:
    """Toate potrivirile de 13 cifre, cautate linie cu linie.

    Spatiile interne se scot inainte de cautare: OCR-ul baga uneori spatii in
    mijlocul unui numar, dar rareori rupe randul. Cautarea ramane pe linie
    tocmai ca sa nu lipim cifrele de la capatul unui rand cu cele de la
    inceputul urmatorului si sa inventam un CNP care nu e pe document.
    """
    candidati: list[str] = []
    for linie in text.splitlines():
        candidati.extend(CNP_REGEX.findall(DOAR_CIFRE.sub("", linie)))
    return candidati


def cel_mai_frecvent(candidati: list[str], incercari: int) -> tuple[str | None, float]:
    """CNP-ul care apare cel mai des, si cat de mult au fost de acord incercarile.

    Forma asta de incredere are sens **numai pentru Tesseract**, unde acelasi
    document se citeste de mai multe ori, cu preprocesari diferite: cand toate
    incercarile cad pe acelasi CNP, e mai mult decat o coincidenta. Nu masoara
    cat de lizibil e buletinul, ci cat de stabil e motorul.

    Azure raporteaza incredere pe cuvant, deci foloseste `din_cuvinte`.
    """
    if not candidati:
        return None, 0.0

    castigator, frecventa = Counter(candidati).most_common(1)[0]
    return castigator, min(1.0, frecventa / max(incercari, 1))


def din_cuvinte(cuvinte: list[tuple[str, float]]) -> tuple[str | None, float]:
    """CNP-ul si increderea lui, din cuvintele raportate de motor.

    `cuvinte` sunt perechi (text, incredere) in ordinea de citire. Increderea
    intoarsa e media cuvintelor care chiar compun CNP-ul — nu a paginii intregi:
    un buletin poate fi citit prost la nume si perfect la cifre, iar pe noi ne
    intereseaza cifrele.

    Se incearca si ferestre de cuvinte alaturate, fiindca motorul rupe uneori
    numarul in doua ("1970101" + "221144").
    """
    for lungime in range(1, CUVINTE_LIPITE_MAXIM + 1):
        for inceput in range(len(cuvinte) - lungime + 1):
            fereastra = cuvinte[inceput : inceput + lungime]
            cifre = DOAR_CIFRE.sub("", "".join(text for text, _ in fereastra))

            potrivire = CNP_REGEX.fullmatch(cifre)
            if potrivire:
                increderi = [incredere for _, incredere in fereastra]
                return potrivire.group(), sum(increderi) / len(increderi)

    return None, 0.0

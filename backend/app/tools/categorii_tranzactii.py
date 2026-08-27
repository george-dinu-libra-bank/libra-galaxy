"""Categorisire determinista a tranzactiilor, dupa descriere/contraparte —
aceeasi ratiune ca orchestration/intent.py: o tabela de cuvinte-cheie e
gratuita, instanta, reproductibila si testabila unitar, spre deosebire de a
lasa modelul sa ghiceasca o categorie (risc de inventie, CLAUDE.md #25).

Ordine: cele mai specifice categorii primele — un comerciant de benzina nu
trebuie sa cada la "cumparaturi" doar pentru ca amandoua sunt plati de card.
"""

from __future__ import annotations

import re
import unicodedata

CATEGORIE_IMPLICITA = "altele"

# Acelasi tipar ca in agents/credit_advisor.py::_SUMA — mutat aici ca sa fie
# reutilizat, nu duplicat, de tools/banking_tools.py::find_transaction_for_receipt.
SUMA_PATTERN = re.compile(r"(\d[\d.\s]{2,})\s*(?:lei|ron)?", re.IGNORECASE)


def extrage_suma(text: str) -> float | None:
    """Prima suma plauzibila dintr-un text liber (ex. "150 lei, era pentru
    restaurant"), sau None daca nu gasim nimic. Spre deosebire de credit_advisor
    (care ignora sub 1000, aproape sigur o durata), o chitanta poate fi orice
    suma pozitiva — fara prag minim."""
    for potrivire in SUMA_PATTERN.finditer(text):
        brut = potrivire.group(1).replace(".", "").replace(" ", "").strip()
        if brut.isdigit() and int(brut) > 0:
            return float(brut)
    return None


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


_CATEGORII: list[tuple[str, tuple[str, ...]]] = [
    (
        "salariu",
        ("salariu", "salary", "payroll", "salar "),
    ),
    (
        "locuinta",
        (
            "chirie", "rent ", "intretinere", "asociatia de proprietari", "rate apartament",
            "credit ipotecar", "ipotecar",
        ),
    ),
    (
        "utilitati",
        (
            "factura", "utilitati", "electrica", "enel", "engie", "e.on", "apa nova", "gaz",
            "vodafone", "orange", "telekom", "digi ", "curent electric", "salubritate",
        ),
    ),
    (
        # Radacini, nu doar comercianti — verificat live ca "drum"/"revizie"/
        # "anvelope" etc. cadeau pe "altele" desi "benzina" mergea deja.
        "masina",
        (
            "benzina", "combustibil", "motorina", "gpl", "omv", "petrom", "mol ", "rompetrol",
            "parcare", "service auto", "vulcanizare", "rovinieta", "vinieta", "asigurare auto",
            "casco", "drum", "auto ", "revizie", "anvelop", "cauciuc", "itp", "autostrada",
            "alimentare auto", "spalatorie auto",
        ),
    ),
    (
        "restaurant",
        (
            "restaurant", "cafenea", "cafea", "mcdonald", "kfc", "pizza", "starbucks",
            "bar ", "fast food", "bistro", "food delivery", "glovo", "tazz",
        ),
    ),
    (
        "sanatate",
        ("farmaci", "spital", "clinica", "cabinet medical", "dentist", "policlinica"),  # farmaci: farmacie/farmacia/farmacist
    ),
    (
        "abonamente",
        ("abonament", "netflix", "spotify", "hbo", "disney+", "subscription", "youtube premium"),
    ),
    (
        "cumparaturi",
        (
            "mall", "shop", "magazin", "emag", "altex", "zara", "h&m", "cumparaturi",
            "market", "kaufland", "carrefour", "lidl", "mega image", "auchan", "ikea",
        ),
    ),
    (
        "transfer",
        ("transfer", "virament"),
    ),
]


# Singura sursa de adevar pentru categoriile valide — folosita si de validarea
# din api/routes/analiza.py (categoria manuala trimisa de utilizator) inainte
# de scriere, ca sa nu ajunga in categorii_manuale_tranzactii o valoare pe care
# categorizeaza() n-o va produce niciodata. Constrangerea CHECK din migratia
# 0043 repeta aceeasi lista in SQL, ca a doua bariera.
CATEGORII_VALIDE: frozenset[str] = frozenset({categorie for categorie, _ in _CATEGORII} | {CATEGORIE_IMPLICITA})


def categorizeaza(descriere: str | None, contraparte: str | None) -> str:
    """Categoria determinista a unei tranzactii, sau CATEGORIE_IMPLICITA daca
    niciun cuvant-cheie nu se potriveste — niciodata inventata de model."""
    text = _normalize(f"{descriere or ''} {contraparte or ''}")

    for categorie, cuvinte in _CATEGORII:
        if any(cuvant in text for cuvant in cuvinte):
            return categorie

    return CATEGORIE_IMPLICITA

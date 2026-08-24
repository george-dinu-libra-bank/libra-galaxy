"""Categorisire determinista a tranzactiilor, dupa descriere/contraparte —
aceeasi ratiune ca orchestration/intent.py: o tabela de cuvinte-cheie e
gratuita, instanta, reproductibila si testabila unitar, spre deosebire de a
lasa modelul sa ghiceasca o categorie (risc de inventie, CLAUDE.md #25).

Ordine: cele mai specifice categorii primele — un comerciant de benzina nu
trebuie sa cada la "cumparaturi" doar pentru ca amandoua sunt plati de card.
"""

from __future__ import annotations

import unicodedata

CATEGORIE_IMPLICITA = "altele"


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
        "masina",
        (
            "benzina", "combustibil", "motorina", "omv", "petrom", "mol ", "rompetrol",
            "parcare", "service auto", "vulcanizare", "rovinieta", "asigurare auto", "casco",
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


def categorizeaza(descriere: str | None, contraparte: str | None) -> str:
    """Categoria determinista a unei tranzactii, sau CATEGORIE_IMPLICITA daca
    niciun cuvant-cheie nu se potriveste — niciodata inventata de model."""
    text = _normalize(f"{descriere or ''} {contraparte or ''}")

    for categorie, cuvinte in _CATEGORII:
        if any(cuvant in text for cuvant in cuvinte):
            return categorie

    return CATEGORIE_IMPLICITA

import pytest

from app.tools.categorii_tranzactii import CATEGORIE_IMPLICITA, categorizeaza


@pytest.mark.parametrize(
    "descriere,contraparte,asteptat",
    [
        ("Salariu august", None, "salariu"),
        ("Chirie apartament", None, "locuinta"),
        ("Factura Enel Energie", None, "utilitati"),
        ("Alimentare Petrom", None, "masina"),
        ("Cina la restaurant", None, "restaurant"),
        ("Reteta", "Farmacia Tei", "sanatate"),
        ("Abonament Netflix lunar", None, "abonamente"),
        (None, "Kaufland Romania", "cumparaturi"),
        ("Transfer economii", None, "transfer"),
        ("Cadou de ziua de nastere", None, CATEGORIE_IMPLICITA),
        (None, None, CATEGORIE_IMPLICITA),
    ],
)
def test_categorizeaza(descriere, contraparte, asteptat):
    assert categorizeaza(descriere, contraparte) == asteptat


def test_categorizeaza_insensibil_la_diacritice_si_majuscule():
    assert categorizeaza("FACTURĂ UTILITĂȚI", None) == "utilitati"
    assert categorizeaza("restaurant", None) == categorizeaza("RESTAURANT", None)

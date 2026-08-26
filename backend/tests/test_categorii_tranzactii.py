import pytest

from app.tools.categorii_tranzactii import CATEGORIE_IMPLICITA, categorizeaza


@pytest.mark.parametrize(
    "descriere,contraparte,asteptat",
    [
        ("Salariu august", None, "salariu"),
        ("Chirie apartament", None, "locuinta"),
        ("Factura Enel Energie", None, "utilitati"),
        ("Alimentare Petrom", None, "masina"),
        # Raportat live: "benzina" mergea deja, dar "drum" si alti termeni
        # auto cadeau pe "altele" — radacini adaugate, nu doar comercianti.
        ("Plata drum spre munte", None, "masina"),
        ("Revizie anuala", None, "masina"),
        ("Anvelope de iarna", None, "masina"),
        ("ITP", None, "masina"),
        ("Vinieta Ungaria", None, "masina"),
        ("Autostrada A1", None, "masina"),
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

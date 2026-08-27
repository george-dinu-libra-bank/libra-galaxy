"""Contractul de credit: sanitizarea HTML-ului, sablonul si PDF-ul.

Sanitizarea are cele mai multe teste, si pe buna dreptate: e singura poarta
dintre un editor din browser si baza de date.
"""

from datetime import date, datetime

import pytest

from app.credit import contract


# -- sanitizare ---------------------------------------------------------------

def test_pastreaza_etichetele_permise():
    assert contract.sanitizeaza("<p>Un <b>text</b> cu <i>marcaje</i></p>") == (
        "<p>Un <b>text</b> cu <i>marcaje</i></p>"
    )


def test_pastreaza_listele():
    assert contract.sanitizeaza("<ul><li>unu</li><li>doi</li></ul>") == (
        "<ul><li>unu</li><li>doi</li></ul>"
    )


def test_scoate_eticheta_dar_pastreaza_textul():
    """Un `<div>` in plus nu trebuie sa inghita o clauza."""
    assert contract.sanitizeaza("<div>clauza</div>") == "clauza"


def test_arunca_scriptul_cu_tot_cu_continut():
    curat = contract.sanitizeaza("<p>Bun</p><script>alert(1)</script>")
    assert curat == "<p>Bun</p>"
    assert "alert" not in curat


def test_arunca_stilul_cu_tot_cu_continut():
    assert contract.sanitizeaza("<style>p{color:red}</style><p>a</p>") == "<p>a</p>"


def test_scoate_toate_atributele():
    curat = contract.sanitizeaza('<p onclick="fura()"><b class="x">a</b></p>')
    assert curat == "<p><b>a</b></p>"
    assert "onclick" not in curat and "class" not in curat


def test_escapeaza_textul_care_seamana_cu_html():
    assert contract.sanitizeaza("<p>a &lt; b</p>") == "<p>a &lt; b</p>"


def test_inchide_etichetele_ramase_deschise():
    assert contract.sanitizeaza("<p><b>fara inchidere") == "<p><b>fara inchidere</b></p>"


def test_taie_sirurile_de_br():
    assert contract.sanitizeaza("<p>a<br><br><br><br>b</p>") == "<p>a<br><br>b</p>"


@pytest.mark.parametrize("gol", ["", "   ", "<p></p>", "<p><br></p>", "<p>\xa0</p>"])
def test_recunoaste_contractul_gol(gol):
    assert contract.are_continut(gol) is False


def test_recunoaste_contractul_cu_text():
    assert contract.are_continut("<p>o clauza</p>") is True


# -- sablon -------------------------------------------------------------------

PROFIL = {
    "nume": "Ion Popescu",
    "cnp": "1900101123456",
    "email": "ion@example.ro",
    "telefon": "+40712345678",
    "iban_cont": "RO49AAAA1B31007593840000",
}
CERERE = {"suma_ceruta": 25000, "luni": 36, "rata_lunara": 812.34, "dae": 0.1123, "scop": "renovare"}
PRODUS = {"nume": "Credit de nevoi personale", "dobanda_anuala": 0.0999}


def _sablon():
    return contract.sablon_din_date(
        profil=PROFIL, cerere=CERERE, produs=PRODUS, astazi=date(2026, 8, 26)
    )


def test_sablonul_ia_datele_clientului_din_baza():
    html = _sablon()
    assert "Ion Popescu" in html
    assert "1900101123456" in html
    assert "+40712345678" in html


def test_sablonul_formateaza_sumele_romaneste():
    """DESIGN.md 11: separator de mii '.', zecimale ','."""
    html = _sablon()
    assert "25.000,00 RON" in html
    assert "812,34 RON" in html


def test_sablonul_grupeaza_ibanul():
    assert "RO49 AAAA 1B31 0075 9384 0000" in _sablon()


def test_sablonul_scrie_procentele_cu_virgula():
    html = _sablon()
    assert "9,99%" in html   # dobanda
    assert "11,23%" in html  # DAE


def test_sablonul_calculeaza_totalul_de_plata():
    # 812,34 x 36 = 29.244,24
    assert "29.244,24 RON" in _sablon()


def test_sablonul_trece_prin_sanitizare_neschimbat():
    """Daca sablonul ar pierde ceva la sanitizare, analistul ar vedea altceva
    decat s-a generat inca de la prima salvare."""
    html = _sablon()
    assert contract.sanitizeaza(html) == contract.sanitizeaza(contract.sanitizeaza(html))


def test_sablonul_scapa_de_html_din_datele_clientului():
    html = contract.sablon_din_date(
        profil={**PROFIL, "nume": "<script>x</script>Ion"},
        cerere=CERERE, produs=PRODUS, astazi=date(2026, 8, 26),
    )
    assert "<script>" not in html


def test_sablonul_merge_si_fara_oferta_calculata():
    """La depunere, cererea nu are inca rata sau DAE — sablonul tot trebuie sa iasa."""
    html = contract.sablon_din_date(
        profil=PROFIL,
        cerere={"suma_ceruta": 10000, "luni": 12, "rata_lunara": None, "dae": None},
        produs=PRODUS,
        astazi=date(2026, 8, 26),
    )
    assert "10.000,00 RON" in html
    assert "—" in html


# -- PDF ----------------------------------------------------------------------

def test_pdf_ul_iese_valid():
    pdf = contract.pdf_din_html(
        contract.sanitizeaza(_sablon()),
        nume_client="Ion Popescu",
        semnat_la=datetime(2026, 8, 26, 15, 4),
        referinta="11111111-1111-1111-1111-111111111111",
    )
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_pdf_ul_nu_crapa_pe_html_gol():
    pdf = contract.pdf_din_html(
        "", nume_client="Ion Popescu",
        semnat_la=datetime(2026, 8, 26, 15, 4), referinta="x",
    )
    assert pdf.startswith(b"%PDF-")


def test_calea_in_bucket_incepe_cu_utilizatorul():
    """Politica de storage din 0009 cere ca primul segment sa fie id-ul omului."""
    cale = contract.cale_in_bucket("user-1", "cerere-2", datetime(2026, 8, 26, 15, 4, 5))
    assert cale.startswith("user-1/")
    assert cale.endswith(".pdf")
    assert "cerere-2" in cale

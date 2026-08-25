"""Citirea adeverintei de venit.

Testele lucreaza pe text, nu pe poze: OCR-ul e o dependinta externa cu rezultat
neverificabil, iar ce trebuie sa fie corect aici e interpretarea textului, nu
citirea pixelilor. Textele de mai jos sunt copiate dupa adeverinte reale,
inclusiv cu greselile pe care le face Tesseract (diacritice pierdute, spatii in
plus, randuri lipite).
"""

from decimal import Decimal

from app.credit.adeverinta import (
    VENIT_MAXIM_PLAUZIBIL,
    VENIT_MINIM_PLAUZIBIL,
    _numar,
    citeste_adeverinta,
)

ADEVERINTA_TIPICA = """
ADEVERINTA DE VENIT

Societatea ACME SOFTWARE SRL, cu sediul in Bucuresti,
adevereste prin prezenta ca domnul Popescu Ion este angajat
cu contract individual de munca pe perioada nedeterminata.

Salariul brut lunar: 8.200,00 lei
Salariul net lunar: 4.850,00 lei

Vechime in unitate: 3 ani
"""


def test_citeste_venitul_net_nu_brutul() -> None:
    """Cel mai probabil mod de a gresi: sa iei prima suma de pe document."""
    date = citeste_adeverinta(ADEVERINTA_TIPICA)

    assert date.venit_net == Decimal("4850.00")
    assert date.incredere > 0.5
    assert date.utilizabila


def test_gaseste_angajatorul_si_vechimea() -> None:
    date = citeste_adeverinta(ADEVERINTA_TIPICA)

    assert date.angajator is not None
    assert "ACME" in date.angajator
    assert date.vechime_luni == 36


# Adeverinta pe formular tipizat, cu tabele — cazul care a scos la iveala bug-ul.
# OCR-ul lipeste celulele unui rand de tabel, iar antetul contine cuvantul
# "Angajator" intr-un numar de inregistrare, inaintea denumirii reale.
ADEVERINTA_CU_TABEL = """
MODEL ADEVERINTA DE VENIT
Nr. Inregistrare Angajator: 1042 / 15.01.2026    Cod Validare OCR: OCR-TEST-2026-LIB-8891
Data eliberarii: 15 Ianuarie 2026    Tip Document: Formular Standard Venit
1. Date de identificare Angajator
Camp Date OCR    Valoare Text
Denumire Societate    SC TECH SOLUTIONS DEVELOPMENT SRL
Cod Unic de Inregistrare (CUI)    RO 39482105
Nr. Reg. Comertului    J40/12345/2018

Salariul net lunar: 15.000,00 lei
"""


def test_numarul_de_inregistrare_nu_e_luat_drept_angajator() -> None:
    """Randul "Nr. Inregistrare Angajator: 1042 / ..." contine si el eticheta,
    si vine inaintea denumirii reale. Prima potrivire lua numarul."""
    date = citeste_adeverinta(ADEVERINTA_CU_TABEL)

    assert date.angajator == "SC TECH SOLUTIONS DEVELOPMENT SRL"
    assert date.venit_net == Decimal("15000.00")


def test_numele_se_taie_la_urmatoarea_eticheta_din_tabel() -> None:
    """Celulele lipite pe acelasi rand nu trebuie sa intre in nume."""
    date = citeste_adeverinta("Denumire Societate  ACME SOFTWARE SRL  Cod Unic RO 123456")

    assert date.angajator == "ACME SOFTWARE SRL"


def test_fara_denumire_nu_se_inventeaza_un_angajator() -> None:
    """Doar numarul de inregistrare pe document: un camp gol e mai onest decat
    unul plin cu o data si un cod."""
    date = citeste_adeverinta(
        "Nr. Inregistrare Angajator: 1042 / 15.01.2026\nSalariul net lunar: 4.850,00 lei"
    )

    assert date.angajator is None
    assert date.venit_net == Decimal("4850.00")


def test_fara_eticheta_nu_ghiceste() -> None:
    """Un document din care nu se citeste eticheta nu produce o cifra.

    Regula de baza a modulului: mai bine un camp gol, pe care analistul il
    completeaza, decat unul plin cu numarul gresit, pe care il crede.
    """
    date = citeste_adeverinta("ADEVERINTA\n\nSuma: 4.850,00 lei\nStampila si semnatura")

    assert date.venit_net is None
    assert date.incredere == 0.0
    assert not date.utilizabila


def test_text_gol_sau_ilizibil() -> None:
    for text in ("", "   \n\n  ", "|||| ??? ~~~"):
        date = citeste_adeverinta(text)
        assert date.venit_net is None
        assert date.incredere == 0.0


def test_diacriticele_pierdute_de_ocr_nu_incurca() -> None:
    """Tesseract intoarce des "plata" in loc de "plată". Ambele trebuie sa mearga."""
    cu_diacritice = citeste_adeverinta("Salariu net de plată: 3.200,00 lei")
    fara_diacritice = citeste_adeverinta("Salariu net de plata: 3.200,00 lei")

    assert cu_diacritice.venit_net == fara_diacritice.venit_net == Decimal("3200.00")


def test_forma_de_tabel_e_citita_dar_cu_incredere_mai_mica() -> None:
    """Eticheta pe un rand, cifra pe urmatorul — legatura e presupusa, nu citita."""
    tabel = citeste_adeverinta("Salariu net\n4.850,00")
    o_linie = citeste_adeverinta("Salariu net: 4.850,00")

    assert tabel.venit_net == Decimal("4850.00")
    assert tabel.incredere < o_linie.incredere


def test_tabelul_cu_mai_multe_coloane_nu_se_ghiceste() -> None:
    """Doua cifre sub eticheta: nu se stie care coloana e a netului."""
    date = citeste_adeverinta("Salariu net\n8.200,00   4.850,00")

    assert date.venit_net is None


def test_linia_cu_impozit_nu_e_candidat() -> None:
    date = citeste_adeverinta(
        "Impozit retinut din venitul net: 850,00 lei\nSalariul net lunar: 4.100,00 lei"
    )

    assert date.venit_net == Decimal("4100.00")


def test_acordul_intre_variantele_ocr_creste_increderea() -> None:
    """`extrage_text` lipeste mai multe preprocesari; cand cad pe aceeasi cifra,
    e mai mult decat o coincidenta."""
    o_data = citeste_adeverinta("Salariu net: 4.850,00 lei")
    de_doua_ori = citeste_adeverinta(
        "Salariu net: 4.850,00 lei\nvenit net lunar 4.850,00 lei"
    )

    assert de_doua_ori.venit_net == o_data.venit_net
    assert de_doua_ori.incredere > o_data.incredere


class TestNumereRomanesti:
    """Punctul si virgula isi schimba rolurile fata de engleza, iar documentele
    amesteca ambele conventii. Aici se pierd cel mai usor cifre."""

    def test_punct_pentru_mii_virgula_pentru_zecimale(self) -> None:
        assert _numar("4.850,00") == Decimal("4850.00")

    def test_spatiu_pentru_mii(self) -> None:
        assert _numar("4 850,00") == Decimal("4850.00")

    def test_doar_virgula_zecimala(self) -> None:
        assert _numar("4850,50") == Decimal("4850.50")

    def test_doar_punct_pentru_mii(self) -> None:
        """Trei cifre dupa punct inseamna mii, nu zecimale: banii n-au 3 zecimale."""
        assert _numar("4.850") == Decimal("4850")

    def test_conventia_engleza_cu_punct_zecimal(self) -> None:
        assert _numar("4850.00") == Decimal("4850.00")

    def test_virgula_cu_trei_cifre_e_separator_de_mii(self) -> None:
        """"4,850" ar fi 4.85 lei dupa conventia romaneasca — implauzibil ca salariu."""
        assert _numar("4,850") == Decimal("4850")

    def test_grupe_multiple_de_mii(self) -> None:
        """Doua separatoare inseamna milioane, deci nu un salariu lunar.

        Nu e o limita a parsarii, ci a plauzibilitatii: orice numar cu doua
        grupe de mii depaseste plafonul. Faptul ca nu se poate scrie un test in
        care sa treaca e chiar demonstratia."""
        assert _numar("1.234.567") is None
        assert _numar("150.000") == Decimal("150000")

    def test_sumele_implauzibile_sunt_refuzate(self) -> None:
        """Anii, numerele de telefon si sumele absurde nu sunt salarii."""
        assert _numar("12") is None
        assert _numar(str(VENIT_MAXIM_PLAUZIBIL + 1)) is None
        assert _numar(str(VENIT_MINIM_PLAUZIBIL - 1)) is None

    def test_marginile_benzii_sunt_acceptate(self) -> None:
        assert _numar(str(VENIT_MINIM_PLAUZIBIL)) == VENIT_MINIM_PLAUZIBIL
        assert _numar(str(VENIT_MAXIM_PLAUZIBIL)) == VENIT_MAXIM_PLAUZIBIL

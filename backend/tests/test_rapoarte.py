"""Raportul: continut determinist, formate valide, avertismentul la locul lui."""

import csv
import io
from datetime import datetime, timezone

from app.ml.neregularitati import Neregularitate
from app.rapoarte import csv_raport, pdf_raport
from app.services.raport_service import Raport

GENERAT_LA = datetime(2026, 8, 20, 9, 30, tzinfo=timezone.utc)


def _constatare(tip: str, suma: float, scor: float, comerciant: str = "kaufland") -> Neregularitate:
    return Neregularitate(
        id_tranzactie=f"{tip}-{suma}",
        data="2026-08-10",
        suma=suma,
        valuta="RON",
        comerciant=comerciant,
        tip=tip,
        explicatie=f"Explicatie pentru {tip}.",
        scor=scor,
    )


def _raport(constatari: list[Neregularitate] | None = None, sinteza: str | None = None) -> Raport:
    constatari = constatari if constatari is not None else [
        _constatare("suma_neobisnuita", 2450.0, 45.41),
        _constatare("plata_dublata", 349.9, 10.0, "emag"),
        _constatare("tipar_neobisnuit", 264.15, 4.3, "dedeman"),
    ]
    return Raport(
        id_utilizator="84caf4a1-a7f5-4b95-bd83-836bbdb541d6",
        nume="Ana Popescu",
        email="ana@exemplu.ro",
        iban="RO49LIBR1B310075938400",
        zile=180,
        generat_la=GENERAT_LA,
        constatari=constatari,
        total_tranzactii=448,
        sinteza=sinteza,
        pe_tip={"suma_neobisnuita": 1, "plata_dublata": 1, "tipar_neobisnuit": 1},
    )


def test_pdf_ul_e_un_pdf_valid() -> None:
    continut = pdf_raport.randeaza(_raport())

    assert continut.startswith(b"%PDF-")
    assert continut.rstrip().endswith(b"%%EOF")


def test_acelasi_raport_da_acelasi_csv() -> None:
    """Un raport pe baza caruia se blocheaza un cont trebuie sa se poata reface."""
    assert csv_raport.randeaza(_raport()) == csv_raport.randeaza(_raport())


def test_csv_ul_contine_toate_constatarile() -> None:
    continut = csv_raport.randeaza(_raport()).decode("utf-8-sig")
    randuri = list(csv.DictReader(io.StringIO(continut)))

    assert len(randuri) == 3
    assert randuri[0]["suma"] == "2450.00"
    assert randuri[0]["tip"] == "suma_neobisnuita"
    assert randuri[0]["tip_afisat"] == "Suma neobisnuita"


def test_csv_ul_are_bom_pentru_excel() -> None:
    """Fara BOM, Excel pe Windows strica diacriticele."""
    assert csv_raport.randeaza(_raport()).startswith(b"\xef\xbb\xbf")


def test_raportul_gol_ramane_valid() -> None:
    gol = _raport(constatari=[])

    assert pdf_raport.randeaza(gol).startswith(b"%PDF-")
    assert csv_raport.randeaza(gol).decode("utf-8-sig").strip() == ",".join(csv_raport.COLOANE)


def test_sumele_se_aduna_peste_constatari() -> None:
    raport = _raport()

    assert raport.suma_semnalata == 3064.05
    assert raport.scor_maxim == 45.41


def test_numele_fisierelor_contin_data() -> None:
    raport = _raport()

    assert pdf_raport.nume_fisier(raport).endswith("-2026-08-20.pdf")
    assert csv_raport.nume_fisier(raport).endswith("-2026-08-20.csv")


def test_pdf_ul_creste_cand_are_sinteza() -> None:
    fara = pdf_raport.randeaza(_raport())
    cu = pdf_raport.randeaza(_raport(sinteza="Trei semnalari, toate in aceeasi saptamana."))

    assert len(cu) > len(fara)

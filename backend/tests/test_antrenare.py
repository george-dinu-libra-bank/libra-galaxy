import pathlib
from uuid import uuid4

import pytest

from app.ml.antrenare import _din_csv, _exemple

ANTET = "id,suma,valuta,descriere,creat_la,id_user_send,id_user_recieve\n"
EU = uuid4()


def _scrie(tmp_path: pathlib.Path, continut: str) -> pathlib.Path:
    cale = tmp_path / "tranzactii.csv"
    cale.write_text(continut, encoding="utf-8")
    return cale


def test_citeste_randurile_din_csv(tmp_path: pathlib.Path) -> None:
    cale = _scrie(
        tmp_path,
        ANTET
        + f"{uuid4()},42.50,RON,Kaufland ref 123,2026-01-05T12:00:00+00:00,{EU},\n"
        + f"{uuid4()},8500,RON,Salariu,2026-01-05T09:00:00+00:00,,{EU}\n",
    )

    randuri = _din_csv(cale)

    assert len(randuri) == 2
    assert randuri[0]["suma"] == "42.50"
    assert randuri[1]["id_user_send"] == ""


def test_randurile_fara_suma_sau_data_sunt_sarite(tmp_path: pathlib.Path) -> None:
    cale = _scrie(
        tmp_path,
        ANTET
        + f"{uuid4()},,RON,Fara suma,2026-01-05T12:00:00+00:00,{EU},\n"
        + f"{uuid4()},30,RON,Fara data,,{EU},\n"
        + f"{uuid4()},55,RON,Buna,2026-01-06T12:00:00+00:00,{EU},\n",
    )

    randuri = _din_csv(cale)

    assert [r["descriere"] for r in randuri] == ["Buna"]


def test_coloanele_in_plus_nu_deranjeaza(tmp_path: pathlib.Path) -> None:
    """Setul de testare are anomalie_asteptata; normalizeaza() ia doar ce-i trebuie."""
    cale = _scrie(
        tmp_path,
        ANTET.rstrip("\n")
        + ",anomalie_asteptata\n"
        + f"{uuid4()},100,RON,Kaufland,2026-01-05T12:00:00+00:00,{EU},,\n"
        + f"{uuid4()},4200,RON,Kaufland,2026-01-09T12:00:00+00:00,{EU},,suma_neobisnuita\n",
    )

    randuri = _din_csv(cale)

    assert len(_din_csv(cale)) == 2
    assert _exemple(randuri)


def test_fisier_inexistent_se_opreste_clar(tmp_path: pathlib.Path) -> None:
    with pytest.raises(SystemExit):
        _din_csv(tmp_path / "lipseste.csv")


def test_fiecare_exemplu_are_cinci_trasaturi() -> None:
    """Vectorul e contractul comun cu inferenta; lungimea lui nu se schimba tacit."""
    randuri = [
        {
            "id": str(uuid4()),
            "suma": 40.0 + i,
            "valuta": "RON",
            "descriere": f"Kaufland ref {1000 + i}",
            "creat_la": f"2026-01-{5 + i:02d}T12:00:00+00:00",
            "id_user_send": str(EU),
            "id_user_recieve": "",
        }
        for i in range(5)
    ]

    exemple = _exemple(randuri)

    # Prima plata la comerciant nu produce exemplu: n-are cu ce fi comparata,
    # iar la inferenta detectorul nici n-o trimite la model.
    assert len(exemple) == 4
    assert all(len(e) == 5 for e in exemple)


def test_incasarile_nu_devin_exemple() -> None:
    """Modelul invata din plati, nu din bani primiti."""
    randuri = [
        {
            "id": str(uuid4()),
            "suma": 8500,
            "valuta": "RON",
            "descriere": "Salariu",
            "creat_la": "2026-01-05T09:00:00+00:00",
            "id_user_send": "",
            "id_user_recieve": str(EU),
        }
    ]

    assert _exemple(randuri) == []

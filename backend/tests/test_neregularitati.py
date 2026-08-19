from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.ml.caracteristici import normalizeaza, normalizeaza_comerciant
from app.ml.neregularitati import DetectorNeregularitati

EU = uuid4()
ALTUL = uuid4()
START = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)


def _rand(zile: int, suma: float, descriere: str, minute: int = 0) -> dict:
    return {
        "id": str(uuid4()),
        "suma": suma,
        "valuta": "RON",
        "descriere": descriere,
        "creat_la": (START + timedelta(days=zile, minutes=minute)).isoformat(),
        "id_user_send": str(EU),
        "id_user_recieve": str(ALTUL),
    }


def _evalueaza(randuri: list[dict]):
    return DetectorNeregularitati().evalueaza(normalizeaza(randuri, EU))


def test_descrierea_se_curata_de_coduri_de_referinta() -> None:
    assert normalizeaza_comerciant("KAUFLAND ref 88213345") == normalizeaza_comerciant(
        "Kaufland REF 90011234"
    )


def test_suma_mult_peste_tipar_e_semnalata() -> None:
    randuri = [_rand(i * 7, 42.0 + i, "Kaufland") for i in range(6)]
    randuri.append(_rand(60, 980.0, "Kaufland"))

    constatari = _evalueaza(randuri)

    assert [c.tip for c in constatari] == ["suma_neobisnuita"]
    assert constatari[0].suma == 980.0


def test_platile_obisnuite_nu_produc_zgomot() -> None:
    randuri = [_rand(i * 7, 40.0 + (i % 3), "Kaufland") for i in range(10)]

    assert _evalueaza(randuri) == []


def test_aceeasi_suma_de_doua_ori_in_cateva_minute() -> None:
    randuri = [_rand(i * 7, 120.0, "Emag") for i in range(5)]
    randuri.append(_rand(40, 120.0, "Emag"))
    randuri.append(_rand(40, 120.0, "Emag", minute=3))

    tipuri = [c.tip for c in _evalueaza(randuri)]

    assert "plata_dublata" in tipuri


def test_incasarile_nu_sunt_analizate() -> None:
    randuri = []
    for i in range(6):
        rand = _rand(i * 7, 5000.0, "Salariu")
        rand["id_user_send"], rand["id_user_recieve"] = str(ALTUL), str(EU)
        randuri.append(rand)

    assert _evalueaza(randuri) == []


def test_sumele_mici_nu_genereaza_alerte() -> None:
    randuri = [_rand(i * 7, 2.0, "Cafea") for i in range(8)]
    randuri.append(_rand(70, 45.0, "Cafea"))

    assert _evalueaza(randuri) == []


def test_prima_plata_obisnuita_la_un_magazin_nou_nu_e_alerta() -> None:
    randuri = [_rand(i * 3, 100.0, "Kaufland") for i in range(8)]
    randuri.append(_rand(40, 180.0, "OMV benzina"))

    assert _evalueaza(randuri) == []


def test_prima_plata_foarte_mare_la_un_magazin_nou_e_alerta() -> None:
    randuri = [_rand(i * 3, 100.0, "Kaufland") for i in range(8)]
    randuri.append(_rand(40, 4200.0, "Bijuterii Lux"))

    assert [c.tip for c in _evalueaza(randuri)] == ["comerciant_nou"]

import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.ml.caracteristici import Plata, normalizeaza, normalizeaza_comerciant, vector
from app.ml.neregularitati import PRAG_SCOR, DetectorNeregularitati, incarca_model

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


# --------------------------------------------------------------------------- #
# Stratul de model. Cele trei verificari statistice de mai sus au prioritate,   #
# deci scenariile de aici sunt construite anume ca ele sa nu se declanseze:     #
# doua plati anterioare la acelasi comerciant (sub MIN_ISTORIC, deci            #
# _suma_atipica se opreste; istoric nevid, deci _comerciant_nou se opreste).    #
# --------------------------------------------------------------------------- #


def _model_antrenat():
    """IsolationForest peste plati obisnuite, ca sa aiba fata de ce sa compare."""
    from sklearn.ensemble import IsolationForest

    obisnuite = [
        Plata(
            id=str(uuid4()),
            moment=START + timedelta(days=i * 3),
            suma=40.0 + (i % 5),
            valuta="RON",
            comerciant="kaufland",
            iesire=True,
        )
        for i in range(60)
    ]
    exemple = [vector(p, obisnuite, obisnuite) for p in obisnuite]

    model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    model.fit(exemple)
    return model


def _randuri_cu_plata_finala(suma: float) -> list[dict]:
    randuri = [_rand(i * 3, 40.0 + i, "Kaufland") for i in range(2)]
    randuri.append(_rand(30, suma, "Kaufland"))
    return randuri


def test_modelul_semnaleaza_o_plata_in_afara_tiparului() -> None:
    detector = DetectorNeregularitati(model=_model_antrenat())

    constatari = detector.evalueaza(
        normalizeaza(_randuri_cu_plata_finala(9000.0), EU)
    )

    # Plata iesita din tipar e cea mai grava, deci prima dupa scor.
    assert constatari[0].tip == "tipar_neobisnuit"
    assert constatari[0].suma == 9000.0


def test_fara_model_aceleasi_randuri_nu_produc_nimic() -> None:
    """Degradarea tacita: fara artefact, stratul statistic ramane singur."""
    randuri = _randuri_cu_plata_finala(9000.0)

    assert DetectorNeregularitati(model=None).evalueaza(normalizeaza(randuri, EU)) == []


def test_scorul_modelului_nu_mai_e_constant() -> None:
    """Inainte scorul era fix PRAG_SCOR, deci constatarile nu se puteau ordona."""
    detector = DetectorNeregularitati(model=_model_antrenat())

    constatare = detector.evalueaza(normalizeaza(_randuri_cu_plata_finala(9000.0), EU))[0]

    assert constatare.scor > PRAG_SCOR


def test_un_model_care_crapa_nu_darama_evaluarea() -> None:
    class ModelStricat:
        def predict(self, _trasaturi):
            raise RuntimeError("artefact corupt")

    detector = DetectorNeregularitati(model=ModelStricat())

    assert detector.evalueaza(normalizeaza(_randuri_cu_plata_finala(9000.0), EU)) == []


def test_mai_multe_plati_intr_o_zi_la_acelasi_magazin() -> None:
    """Sume normale si diferite intre ele: anormal e numai ritmul."""
    randuri = [_rand(60 - i * 7, 50.0, "Glovo") for i in range(6)]
    randuri += [
        _rand(2 - ora / 24, 48.0 + ora, "Glovo") for ora in (0, 2, 4, 6)
    ]

    tipuri = [c.tip for c in _evalueaza(randuri)]

    assert tipuri.count("rafala_de_plati") == 1


def test_trei_plati_intr_o_zi_nu_sunt_inca_o_rafala() -> None:
    randuri = [_rand(60 - i * 7, 50.0, "Glovo") for i in range(6)]
    randuri += [_rand(2 - ora / 24, 48.0 + ora, "Glovo") for ora in (0, 2, 4)]

    assert [c.tip for c in _evalueaza(randuri) if c.tip == "rafala_de_plati"] == []


def test_platile_rare_la_acelasi_magazin_nu_sunt_rafala() -> None:
    randuri = [_rand(60 - i * 7, 50.0, "Glovo") for i in range(10)]

    assert [c.tip for c in _evalueaza(randuri) if c.tip == "rafala_de_plati"] == []


def test_artefactul_se_citeste_o_singura_data(monkeypatch) -> None:
    """Altfel s-ar reciti la fiecare cerere — cateva sute de ms platite degeaba."""
    import app.ml.neregularitati as modul

    incarca_model.cache_clear()
    citiri = 0

    def _load(_cale):
        nonlocal citiri
        citiri += 1
        return object()

    monkeypatch.setattr(modul.Path, "exists", lambda _self: True)
    monkeypatch.setitem(sys.modules, "joblib", SimpleNamespace(load=_load))
    try:
        for _ in range(5):
            DetectorNeregularitati.cu_model_de_pe_disc()
    finally:
        incarca_model.cache_clear()

    assert citiri == 1

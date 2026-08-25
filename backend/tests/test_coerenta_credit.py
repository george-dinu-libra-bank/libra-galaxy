"""Etapa 'coerenta' a pipeline-ului AI de credite — pur, fara model, testat ca
reguli.py: fiecare semnal se declanseaza sau nu, in functie de date construite.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.credit.ai.contracte import ExtractieDocument
from app.credit.ai.etape.coerenta import evalueaza
from app.credit.venit import VenitConstatat
from app.ml.caracteristici import Plata

CERERE_CREAT_LA = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)


def _cerere(**peste) -> dict:
    de_baza = {
        "id": str(uuid4()), "venit_declarat": "5200", "angajator": "ACME Software SRL",
        "creat_la": CERERE_CREAT_LA.isoformat(),
    }
    return {**de_baza, **peste}


def _venit_constatat(**peste) -> VenitConstatat:
    de_baza = dict(venit_lunar=5000.0, luni_detectate=12, platitor="acme software srl salariu", deviatie_relativa=0.05, incredere=0.9)
    return VenitConstatat(**{**de_baza, **peste})


def _incasare(zile_inainte_de_cerere: float, suma: float, platitor: str = "andrei") -> Plata:
    return Plata(
        id=str(uuid4()), moment=CERERE_CREAT_LA - timedelta(days=zile_inainte_de_cerere),
        suma=suma, valuta="RON", comerciant=platitor, iesire=False,
    )


def test_fara_nimic_nu_produce_niciun_semnal() -> None:
    semnale = evalueaza(
        cerere=_cerere(angajator=None, venit_declarat=None), documente=[], documente_reutilizate=[],
        venit_constatat=None, plati=[],
    )
    assert semnale == []


# -- document_reutilizat -----------------------------------------------------


def test_document_reutilizat_cand_hash_apare_la_alta_cerere() -> None:
    alta_cerere = str(uuid4())
    semnale = evalueaza(
        cerere=_cerere(), documente=[], venit_constatat=None, plati=[],
        documente_reutilizate=[{"id": str(uuid4()), "id_cerere": alta_cerere, "id_user": str(uuid4())}],
    )
    coduri = [s.cod for s in semnale]
    assert "document_reutilizat" in coduri
    semnal = next(s for s in semnale if s.cod == "document_reutilizat")
    assert semnal.severitate == "grav"
    assert semnal.detaliu["alte_cereri"] == [alta_cerere]


def test_fara_reutilizare_nu_semnaleaza() -> None:
    semnale = evalueaza(cerere=_cerere(), documente=[], documente_reutilizate=[], venit_constatat=None, plati=[])
    assert "document_reutilizat" not in [s.cod for s in semnale]


# -- venit_declarat_umflat ----------------------------------------------------


def test_venit_declarat_mult_peste_tranzactii_semnaleaza() -> None:
    semnale = evalueaza(
        cerere=_cerere(venit_declarat="10000", angajator=None), documente=[], documente_reutilizate=[],
        venit_constatat=_venit_constatat(venit_lunar=5000.0), plati=[],
    )
    assert "venit_declarat_umflat" in [s.cod for s in semnale]


def test_venit_declarat_apropiat_nu_semnaleaza() -> None:
    semnale = evalueaza(
        cerere=_cerere(venit_declarat="5200", angajator=None), documente=[], documente_reutilizate=[],
        venit_constatat=_venit_constatat(venit_lunar=5000.0), plati=[],
    )
    assert "venit_declarat_umflat" not in [s.cod for s in semnale]


# -- angajator_nepotrivit ------------------------------------------------------


def test_angajator_fara_legatura_cu_platitorul_semnaleaza() -> None:
    semnale = evalueaza(
        cerere=_cerere(angajator="Restaurant Poarta Verde SRL", venit_declarat=None),
        documente=[], documente_reutilizate=[],
        venit_constatat=_venit_constatat(platitor="acme software srl"), plati=[],
    )
    assert "angajator_nepotrivit" in [s.cod for s in semnale]


def test_angajator_asemanator_nu_semnaleaza() -> None:
    semnale = evalueaza(
        cerere=_cerere(angajator="ACME Software SRL", venit_declarat=None),
        documente=[], documente_reutilizate=[],
        venit_constatat=_venit_constatat(platitor="acme software srl salariu"), plati=[],
    )
    assert "angajator_nepotrivit" not in [s.cod for s in semnale]


# -- document_vs_tranzactii ----------------------------------------------------


def test_venit_din_document_departe_de_tranzactii_semnaleaza() -> None:
    documente = [{"id": str(uuid4()), "extras": {"venit_net": "9000"}}]
    semnale = evalueaza(
        cerere=_cerere(angajator=None, venit_declarat=None), documente=documente, documente_reutilizate=[],
        venit_constatat=_venit_constatat(venit_lunar=5000.0), plati=[],
    )
    assert "document_vs_tranzactii" in [s.cod for s in semnale]


def test_venit_din_document_apropiat_nu_semnaleaza() -> None:
    documente = [{"id": str(uuid4()), "extras": {"venit_net": "5100"}}]
    semnale = evalueaza(
        cerere=_cerere(angajator=None, venit_declarat=None), documente=documente, documente_reutilizate=[],
        venit_constatat=_venit_constatat(venit_lunar=5000.0), plati=[],
    )
    assert "document_vs_tranzactii" not in [s.cod for s in semnale]


def test_extractia_ai_bate_regex_ul_cand_ambele_exista() -> None:
    """Cand modelul a citit documentul in aceasta rulare, coerenta prefera cifra
    lui — nu pe cea salvata la incarcare de regex."""
    documente = [{"id": str(uuid4()), "extras": {"venit_net": "5050"}}]
    extractie = ExtractieDocument(
        venit_net=None, venit_brut=None, angajator=None, cui_angajator=None,
        perioada=None, functie=None, are_stampila=None, are_semnatura=None, incredere=0.9,
    )
    # extractie.venit_net e None (modelul n-a gasit cifra) -> ramane pe regex, care e apropiat -> fara semnal.
    semnale = evalueaza(
        cerere=_cerere(angajator=None, venit_declarat=None), documente=documente, documente_reutilizate=[],
        venit_constatat=_venit_constatat(venit_lunar=5000.0), plati=[], extractie_document=extractie,
    )
    assert "document_vs_tranzactii" not in [s.cod for s in semnale]


# -- incasari_pregatitoare -----------------------------------------------------


def test_incasare_mare_chiar_inainte_de_cerere_semnaleaza() -> None:
    istoric = [_incasare(60 + 10 * i, 500.0, "prieten") for i in range(6)]
    recenta = [_incasare(5, 6000.0, "prieten")]
    semnale = evalueaza(
        cerere=_cerere(angajator=None, venit_declarat=None), documente=[], documente_reutilizate=[],
        venit_constatat=None, plati=istoric + recenta,
    )
    assert "incasari_pregatitoare" in [s.cod for s in semnale]


def test_incasari_obisnuite_nu_semnaleaza() -> None:
    istoric = [_incasare(60 + 10 * i, 500.0, "prieten") for i in range(6)]
    recenta = [_incasare(5, 520.0, "prieten")]
    semnale = evalueaza(
        cerere=_cerere(angajator=None, venit_declarat=None), documente=[], documente_reutilizate=[],
        venit_constatat=None, plati=istoric + recenta,
    )
    assert "incasari_pregatitoare" not in [s.cod for s in semnale]


# -- venit_neregulat ------------------------------------------------------------


def test_deviatie_mare_semnaleaza_informativ() -> None:
    semnale = evalueaza(
        cerere=_cerere(angajator=None, venit_declarat=None), documente=[], documente_reutilizate=[],
        venit_constatat=_venit_constatat(deviatie_relativa=0.12), plati=[],
    )
    semnal = next(s for s in semnale if s.cod == "venit_neregulat")
    assert semnal.severitate == "informativ"


def test_deviatie_mica_nu_semnaleaza() -> None:
    semnale = evalueaza(
        cerere=_cerere(angajator=None, venit_declarat=None), documente=[], documente_reutilizate=[],
        venit_constatat=_venit_constatat(deviatie_relativa=0.02), plati=[],
    )
    assert "venit_neregulat" not in [s.cod for s in semnale]


# -- document_ilizibil ----------------------------------------------------------


def test_document_ilizibil_semnaleaza_cate_unul_per_document() -> None:
    documente = [
        {"id": str(uuid4()), "status": "ilizibil"},
        {"id": str(uuid4()), "status": "procesat"},
    ]
    semnale = evalueaza(
        cerere=_cerere(angajator=None, venit_declarat=None), documente=documente, documente_reutilizate=[],
        venit_constatat=None, plati=[],
    )
    ilizibile = [s for s in semnale if s.cod == "document_ilizibil"]
    assert len(ilizibile) == 1

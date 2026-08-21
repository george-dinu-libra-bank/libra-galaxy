"""Adeverinta de venit: citita de masina, confirmata de om.

Fisier separat de `test_flux_credit.py`, dar cu acelasi depozit fals: fluxul
documentelor e o bucata de sine statatoare, iar amestecat cu restul ar face un
fisier in care nu mai gasesti nimic. Depozitul se importa, nu se rescrie.

Adeverintele de test sunt PDF-uri **adevarate**, generate cu reportlab, nu
`text_din_document` inlocuit cu o pacaleala. Asa trece prin `pypdf` exact ca un
document emis electronic de un angajator — cazul obisnuit — iar testul ramane si
rapid, si determinist, fara sa cheme Tesseract.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    UserContext,
    cere_administrator,
    get_credit_service,
    get_current_user,
)
from app.main import app
from app.services.credit_service import CreditService
from tests.test_flux_credit import ID_USER, DepozitFals, _cerere


def _pdf_adeverinta(net: str = "4.850,00") -> bytes:
    from reportlab.pdfgen import canvas

    memorie = io.BytesIO()
    pagina = canvas.Canvas(memorie)
    for indice, linie in enumerate([
        "ADEVERINTA DE VENIT",
        "Societatea ACME SOFTWARE SRL adevereste prin prezenta",
        "ca domnul Test Testescu este angajat cu contract nedeterminat.",
        "Salariul brut lunar: 8.200,00 lei",
        "Salariul net lunar: " + net + " lei",
        "Vechime in unitate: 3 ani",
    ]):
        pagina.drawString(70, 800 - indice * 24, linie)
    pagina.save()
    return memorie.getvalue()


@pytest.fixture
def depozit() -> DepozitFals:
    """Cineva caruia banca nu-i vede salariul: freelancer, sau nou-venit."""
    return DepozitFals(luni_salariu=0)


@pytest.fixture
def client(depozit: DepozitFals):
    """Acelasi om e si client, si analist.

    Ar fi mai realist cu doi utilizatori, dar aici se verifica fluxul datelor,
    nu bariera de acces — aceea e testata in `test_rute_admin.py`, unde un cont
    fara rol primeste 403.
    """
    utilizator = UserContext(user_id=ID_USER, access_token="test")
    app.dependency_overrides[get_current_user] = lambda: utilizator
    app.dependency_overrides[cere_administrator] = lambda: utilizator
    app.dependency_overrides[get_credit_service] = lambda: CreditService(depozit)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _incarca(client, id_cerere: str, net: str = "4.850,00") -> dict:
    raspuns = client.post(
        "/api/v1/credite/cereri/" + id_cerere + "/documente",
        files={"fisier": ("adeverinta.pdf", _pdf_adeverinta(net), "application/pdf")},
    )
    assert raspuns.status_code == 200, raspuns.text
    return raspuns.json()


def _cerere_evaluata(client) -> str:
    id_cerere = _cerere(client)
    client.post("/api/v1/credite/cereri/" + id_cerere + "/evalueaza")
    return id_cerere


# ---------------------------------------------------------------------------
# Cand se cere documentul
# ---------------------------------------------------------------------------


def test_evaluarea_cere_document_cand_banca_nu_vede_venitul(client) -> None:
    """Semnalul dupa care wizard-ul stie sa ceara o adeverinta."""
    id_cerere = _cerere(client)
    decizie = client.post("/api/v1/credite/cereri/" + id_cerere + "/evalueaza").json()

    assert decizie["cere_document"] is True


def test_cine_are_salariul_in_cont_nu_e_intrebat_de_hartii() -> None:
    """Banca nu cere dovezi pentru ce vede deja intrand in cont."""
    depozit = DepozitFals()  # cu salariu lunar detectabil
    utilizator = UserContext(user_id=ID_USER, access_token="test")
    app.dependency_overrides[get_current_user] = lambda: utilizator
    app.dependency_overrides[get_credit_service] = lambda: CreditService(depozit)
    try:
        client = TestClient(app)
        id_cerere = _cerere(client)
        decizie = client.post("/api/v1/credite/cereri/" + id_cerere + "/evalueaza").json()
    finally:
        app.dependency_overrides.clear()

    assert decizie["cere_document"] is False


# ---------------------------------------------------------------------------
# Citit, dar nu crezut
# ---------------------------------------------------------------------------


def test_documentul_e_citit_dar_nu_intra_singur_in_decizie(
    client, depozit: DepozitFals
) -> None:
    """Invariantul care tine tot fluxul in picioare.

    Parserul citeste corect 4.850 lei si o pune in `extras` — dar nu se scrie
    nicio verificare de venit. Fara un om care sa confirme, cifra n-are niciun
    efect asupra scorului. Daca testul asta cade, o poza citita gresit poate da
    un credit pe date inventate.
    """
    id_cerere = _cerere_evaluata(client)

    document = _incarca(client, id_cerere)

    assert document["status"] == "procesat"
    assert document["extras"]["venit_net"] == "4850.00"
    assert document["extras"]["angajator"] is not None
    assert document["venit_confirmat"] is None
    assert not [v for v in depozit.verificari_scrise if v["sursa"] == "adeverinta"]


def test_brutul_de_pe_acelasi_document_nu_e_confundat_cu_netul(client) -> None:
    """Adeverinta are ambele sume; se ia cea corecta, nu prima."""
    document = _incarca(client, _cerere_evaluata(client))

    assert document["extras"]["venit_net"] == "4850.00"


def test_documentul_ilizibil_nu_propune_nimic(client) -> None:
    id_cerere = _cerere_evaluata(client)

    raspuns = client.post(
        "/api/v1/credite/cereri/" + id_cerere + "/documente",
        files={"fisier": ("poza.png", b"\x89PNG" + bytes(64), "image/png")},
    )

    assert raspuns.status_code == 200, raspuns.text
    assert raspuns.json()["status"] == "ilizibil"
    assert raspuns.json()["extras"]["venit_net"] is None


def test_tipurile_neacceptate_sunt_refuzate(client) -> None:
    id_cerere = _cerere_evaluata(client)

    raspuns = client.post(
        "/api/v1/credite/cereri/" + id_cerere + "/documente",
        files={"fisier": ("program.exe", b"MZ", "application/x-msdownload")},
    )

    assert raspuns.status_code == 422, raspuns.text


def test_dosarul_inchis_nu_mai_primeste_documente(client, depozit: DepozitFals) -> None:
    id_cerere = _cerere_evaluata(client)
    depozit.cereri[id_cerere]["status"] = "respinsa"

    raspuns = client.post(
        "/api/v1/credite/cereri/" + id_cerere + "/documente",
        files={"fisier": ("adeverinta.pdf", _pdf_adeverinta(), "application/pdf")},
    )

    assert raspuns.status_code == 422, raspuns.text


# ---------------------------------------------------------------------------
# Confirmarea analistului
# ---------------------------------------------------------------------------


def test_confirmarea_pune_venitul_in_joc_si_reevalueaza(client, depozit: DepozitFals) -> None:
    id_cerere = _cerere_evaluata(client)
    document = _incarca(client, id_cerere)

    raspuns = client.post(
        "/api/v1/admin/credite/documente/" + document["id"] + "/confirma",
        json={"venit_confirmat": "4850.00"},
    )

    assert raspuns.status_code == 200, raspuns.text
    dosar = raspuns.json()
    assert dosar["documente"][0]["status"] == "confirmat"
    assert [v for v in dosar["verificari"] if v["sursa"] == "adeverinta"]
    # Cererea a trecut prin motor din nou, cu venitul confirmat ca intrare.
    assert dosar["cerere"]["venit_folosit"] == "4850.00"


def test_corectia_analistului_se_vede_langa_ce_citise_masina(
    client, depozit: DepozitFals
) -> None:
    """Cand omul corecteaza masina, amandoua cifrele raman.

    `extras` nu se suprascrie: peste sase luni trebuie sa se poata spune nu doar
    ce venit s-a folosit, ci si ca a fost nevoie de o corectie, si cat de mare.
    """
    document = _incarca(client, _cerere_evaluata(client))

    client.post(
        "/api/v1/admin/credite/documente/" + document["id"] + "/confirma",
        json={"venit_confirmat": "5200.00"},
    )

    adeverinta = [v for v in depozit.verificari_scrise if v["sursa"] == "adeverinta"][-1]
    assert adeverinta["detalii"]["citit_de_ocr"] == "4850.00"
    assert adeverinta["detalii"]["corectat"] is True
    assert depozit.documente_scrise[document["id"]]["extras"]["venit_net"] == "4850.00"


def test_a_doua_confirmare_o_inlocuieste_pe_prima(client, depozit: DepozitFals) -> None:
    """Analistul se poate razgandi; ultima confirmare e cea care conteaza."""
    document = _incarca(client, _cerere_evaluata(client))
    cale = "/api/v1/admin/credite/documente/" + document["id"] + "/confirma"

    client.post(cale, json={"venit_confirmat": "4850.00"})
    dosar = client.post(cale, json={"venit_confirmat": "6100.00"}).json()

    assert dosar["cerere"]["venit_folosit"] == "6100.00"


def test_venitul_confirmat_trebuie_sa_fie_pozitiv(client) -> None:
    document = _incarca(client, _cerere_evaluata(client))

    raspuns = client.post(
        "/api/v1/admin/credite/documente/" + document["id"] + "/confirma",
        json={"venit_confirmat": "0"},
    )

    assert raspuns.status_code == 422, raspuns.text


# ---------------------------------------------------------------------------
# Retentia
# ---------------------------------------------------------------------------


def test_fisierul_dispare_dupa_retentie_dar_randul_ramane(
    client, depozit: DepozitFals
) -> None:
    """Ce ocupa spatiu se sterge; ce dovedeste decizia, nu.

    Curatarea e lenesa, ca incasarea ratelor, si porneste dintr-o citire — nu
    exista cron in proiect. Aici o declanseaza coada de analiza.
    """
    id_cerere = _cerere_evaluata(client)
    document = _incarca(client, id_cerere)
    cale = depozit.documente_scrise[document["id"]]["storage_path"]
    assert cale in depozit.fisiere

    depozit.cereri[id_cerere]["status"] = "respinsa"
    depozit.cereri[id_cerere]["finalizat_la"] = (
        datetime.now(timezone.utc) - timedelta(days=31)
    ).isoformat()

    client.get("/api/v1/admin/credite/analiza-manuala")

    rand = depozit.documente_scrise[document["id"]]
    assert cale not in depozit.fisiere
    assert rand["sters_la"] is not None
    assert rand["extras"]["venit_net"] == "4850.00"
    assert rand["hash_fisier"]


def test_dosarul_proaspat_inchis_isi_pastreaza_documentul(
    client, depozit: DepozitFals
) -> None:
    """O contestatie facuta la cald gaseste adeverinta la locul ei."""
    id_cerere = _cerere_evaluata(client)
    document = _incarca(client, id_cerere)
    cale = depozit.documente_scrise[document["id"]]["storage_path"]

    depozit.cereri[id_cerere]["status"] = "respinsa"
    depozit.cereri[id_cerere]["finalizat_la"] = (
        datetime.now(timezone.utc) - timedelta(days=5)
    ).isoformat()

    client.get("/api/v1/admin/credite/analiza-manuala")

    assert cale in depozit.fisiere
    assert depozit.documente_scrise[document["id"]]["sters_la"] is None


def test_dosarul_in_lucru_nu_e_atins_oricat_ar_dura(client, depozit: DepozitFals) -> None:
    """Retentia curge de la inchidere, nu de la incarcare."""
    id_cerere = _cerere_evaluata(client)
    document = _incarca(client, id_cerere)
    cale = depozit.documente_scrise[document["id"]]["storage_path"]

    client.get("/api/v1/admin/credite/analiza-manuala")

    assert cale in depozit.fisiere


def test_curatarea_e_idempotenta(client, depozit: DepozitFals) -> None:
    """Doua citiri la rand nu incearca sa stearga acelasi fisier de doua ori.

    Filtrul `sters_la is null` e singurul lucru care garanteaza asta — la fel ca
    `credit_rate_unica` la incasarea ratelor.
    """
    id_cerere = _cerere_evaluata(client)
    document = _incarca(client, id_cerere)
    depozit.cereri[id_cerere]["status"] = "respinsa"
    depozit.cereri[id_cerere]["finalizat_la"] = (
        datetime.now(timezone.utc) - timedelta(days=31)
    ).isoformat()

    client.get("/api/v1/admin/credite/analiza-manuala")
    sters_la = depozit.documente_scrise[document["id"]]["sters_la"]
    client.get("/api/v1/admin/credite/analiza-manuala")

    assert depozit.documente_scrise[document["id"]]["sters_la"] == sters_la


def test_venitul_doar_declarat_nu_se_aproba_automat(client, depozit: DepozitFals) -> None:
    """Regresie: 85 din 100 si aprobat, pe o cifra scrisa de mana.

    Solicitantul din fixture are grad de indatorare bun, vechime buna si relatie
    lunga cu banca, dar niciun venit vizibil in cont. Scorecard-ul ii dadea 85 —
    `dovada_venit` valoreaza doar 15 din 100 — si trecea pragul de 70. Adica
    oricine putea declara orice suma si primea creditul automat.

    Poarta e separata de punctaj dinadins: umfland ponderea factorului, dovada
    de venit ar fi inceput sa compenseze un grad de indatorare prost.
    """
    id_cerere = _cerere(client)

    decizie = client.post("/api/v1/credite/cereri/" + id_cerere + "/evalueaza").json()

    assert decizie["scor"] >= 70, "fixture-ul nu mai reproduce cazul; scorul a scazut"
    assert decizie["decizie"] == "analiza_manuala"
    assert decizie["rata_lunara"] is None, "o cerere neaprobata nu are oferta"
    assert depozit.cereri[id_cerere]["status"] == "analiza_manuala"


def test_explicatia_spune_omului_ce_are_de_facut(client) -> None:
    """Un sfat generic („un coleg o verifica") e adevarat, dar inutil."""
    id_cerere = _cerere(client)

    decizie = client.post("/api/v1/credite/cereri/" + id_cerere + "/evalueaza").json()

    assert "adeverin" in decizie["explicatie"].lower()


def test_dupa_confirmare_venitul_nu_mai_e_doar_declarat(client, depozit: DepozitFals) -> None:
    """Bucla se inchide: documentul confirmat scoate cererea din zona gri."""
    id_cerere = _cerere_evaluata(client)
    document = _incarca(client, id_cerere, net="9.400,00")

    dosar = client.post(
        "/api/v1/admin/credite/documente/" + document["id"] + "/confirma",
        json={"venit_confirmat": "9400.00"},
    ).json()

    assert dosar["cerere"]["status"] == "oferta"
    assert dosar["cerere"]["rata_lunara"] is not None

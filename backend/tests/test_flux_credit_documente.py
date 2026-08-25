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
from decimal import Decimal
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
    """Venitul confirmat intra in scoring, dar nu emite oferta.

    Confirmarea e completarea unei intrari a motorului, nu o decizie. Scorul se
    recalculeaza si se vede imediat; oferta o emite analistul, apasand "Aproba".
    Altfel un analist care doar valideaza o cifra ar angaja banca fara sa vrea.
    """
    id_cerere = _cerere_evaluata(client)
    document = _incarca(client, id_cerere, net="9.400,00")

    dosar = client.post(
        "/api/v1/admin/credite/documente/" + document["id"] + "/confirma",
        json={"venit_confirmat": "9400.00"},
    ).json()

    cerere = dosar["cerere"]
    assert cerere["status"] == "analiza_manuala"
    # Nicio urma de oferta: un angajament nu poate exista pe jumatate.
    assert cerere["rata_lunara"] is None
    assert cerere["oferta_expira_la"] is None
    # Dar venitul confirmat chiar a intrat in calcul.
    assert Decimal(cerere["venit_folosit"]) == Decimal("9400.00")
    assert cerere["scor"] is not None


# ---------------------------------------------------------------------------
# Analistul are patru iesiri, nu doua
# ---------------------------------------------------------------------------


def _fir(client, id_cerere: str) -> list[dict]:
    raspuns = client.get("/api/v1/credite/cereri/" + id_cerere + "/mesaje")
    assert raspuns.status_code == 200, raspuns.text
    return raspuns.json()


def _decizie(client, id_cerere: str, actiune: str, nota: str | None = None):
    return client.post(
        "/api/v1/admin/credite/cereri/" + id_cerere + "/decizie",
        json={"actiune": actiune, "nota": nota},
    )


def test_cererea_de_acte_muta_mingea_la_client(client, depozit: DepozitFals) -> None:
    """Starea proprie exista ca sa se stie cine asteapta pe cine.

    In 'analiza_manuala' asteapta banca; in 'asteapta_documente' asteapta
    clientul. Cu o singura stare, dosarul ar sta in coada analistului desi el
    n-are ce face, iar clientului i s-ar spune ca „un coleg se uita peste dosar".
    """
    id_cerere = _cerere_evaluata(client)

    raspuns = _decizie(client, id_cerere, "cere_documente", "Avem nevoie de o adeverinta pe ultimele 3 luni.")

    assert raspuns.status_code == 200, raspuns.text
    assert raspuns.json()["status"] == "asteapta_documente"

    fir = _fir(client, id_cerere)
    assert [m["autor"] for m in fir] == ["analist"]
    assert "adeverinta" in fir[0]["text"]


def test_incarcarea_aduce_dosarul_inapoi_la_analist(client, depozit: DepozitFals) -> None:
    """Altfel dosarul ar ramane in 'asteapta_documente' pana si-ar aminti cineva."""
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "cere_documente", "Trimite adeverinta.")

    _incarca(client, id_cerere)

    dosar = client.get("/api/v1/admin/credite/cereri/" + id_cerere).json()
    assert dosar["cerere"]["status"] == "analiza_manuala"


def test_notificarea_nu_schimba_starea_dosarului(client, depozit: DepozitFals) -> None:
    """Un mesaj nu e o decizie si nu muta responsabilitatea."""
    id_cerere = _cerere_evaluata(client)
    inainte = client.get("/api/v1/admin/credite/cereri/" + id_cerere).json()["cerere"]["status"]

    raspuns = _decizie(client, id_cerere, "notifica", "Angajatorul declarat nu se potriveste cu incasarile.")

    assert raspuns.status_code == 200, raspuns.text
    assert raspuns.json()["status"] == inainte

    fir = _fir(client, id_cerere)
    assert "Angajatorul" in fir[-1]["text"]


def test_mesajul_gol_e_refuzat(client, depozit: DepozitFals) -> None:
    """Mesajul e tot ce vede clientul; unul gol l-ar lasa fara sa stie ce sa faca."""
    id_cerere = _cerere_evaluata(client)

    assert _decizie(client, id_cerere, "cere_documente", "   ").status_code == 422
    assert _decizie(client, id_cerere, "notifica", None).status_code == 422


def test_mesajele_se_aduna_nu_se_suprascriu(client, depozit: DepozitFals) -> None:
    """Regresia care a cerut trecerea de la coloana la tabela.

    Cu `mesaj_analist` ca simpla coloana, al doilea mesaj il stergea pe primul:
    un dosar contestat peste sase luni n-ar mai fi putut reconstitui ce s-a cerut.
    """
    id_cerere = _cerere_evaluata(client)

    _decizie(client, id_cerere, "notifica", "Primul mesaj.")
    _decizie(client, id_cerere, "notifica", "Al doilea mesaj.")

    texte = [m["text"] for m in _fir(client, id_cerere)]
    assert texte == ["Primul mesaj.", "Al doilea mesaj."]


def test_clientul_poate_raspunde_in_fir(client, depozit: DepozitFals) -> None:
    """Fara asta, cine nu intelege ce act i se cere n-are unde intreba."""
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "cere_documente", "Trimite adeverinta.")

    raspuns = client.post(
        "/api/v1/credite/cereri/" + id_cerere + "/mesaje",
        json={"text": "Adeverinta de la angajatorul vechi merge?"},
    )

    assert raspuns.status_code == 201, raspuns.text
    fir = _fir(client, id_cerere)
    assert [m["autor"] for m in fir] == ["analist", "client"]


def test_documentul_incarcat_lasa_un_mesaj_in_fir(client, depozit: DepozitFals) -> None:
    """Cronologia dosarului trebuie sa fie una singura: s-a cerut X, a venit Y."""
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "cere_documente", "Trimite adeverinta.")

    document = _incarca(client, id_cerere)

    ultimul = _fir(client, id_cerere)[-1]
    # `sistem`, nu `client`: textul e produs de OCR, nu scris de om.
    assert ultimul["autor"] == "sistem"
    assert ultimul["id_document"] == document["id"]
    # Textul se genereaza din ce a citit OCR-ul, ca analistul sa vada rezultatul
    # fara sa deschida documentul. `_incarca` trimite implicit 4.850,00.
    assert "4850" in ultimul["text"]


def test_firul_supravietuieste_reevaluarii(client, depozit: DepozitFals) -> None:
    """Motivul pentru care firul NU sta in `explicatie`.

    `explicatie` e rescrisa de motor la fiecare reevaluare. Fluxul intreg —
    cer acte, clientul incarca, se reevalueaza — ar sterge mesajul care a
    pornit totul.
    """
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "cere_documente", "Adeverinta de la angajatorul actual.")
    document = _incarca(client, id_cerere)

    client.post(
        "/api/v1/admin/credite/documente/" + document["id"] + "/confirma",
        json={"venit_confirmat": "9400.00"},
    )

    texte = [m["text"] for m in _fir(client, id_cerere)]
    assert "Adeverinta de la angajatorul actual." in texte


def test_mesajul_analistului_produce_si_o_notificare(client, depozit: DepozitFals) -> None:
    """Firul se vede doar daca omul intra in aplicatie.

    Fara notificare, un dosar care asteapta acte poate sta blocat saptamani
    fiindca nimeni nu i-a spus clientului ca s-a cerut ceva. Tipul difera dupa
    cat de urgent e: 'atentionare' cand are de facut ceva, 'info' cand doar afla.
    """
    id_cerere = _cerere_evaluata(client)

    _decizie(client, id_cerere, "cere_documente", "Trimite adeverinta.")
    _decizie(client, id_cerere, "notifica", "Doar o observatie.")

    tipuri = [n["tip"] for n in depozit.notificari_scrise]
    assert tipuri == ["atentionare", "info"]
    # Mesajul poarta la final un marcaj cu id-ul cererii, ca notificarea sa poata
    # duce clientul direct in firul potrivit. Interfata il taie inainte de afisare.
    assert depozit.notificari_scrise[0]["mesaj"].startswith("Trimite adeverinta.")
    assert f"[cerere:{id_cerere}]" in depozit.notificari_scrise[0]["mesaj"]


def test_raspunsul_clientului_nu_produce_notificare(client, depozit: DepozitFals) -> None:
    """Notificarile sunt pentru client. Analistul isi vede firul in dosar, iar
    o notificare pentru fiecare raspuns i-ar umple clopotelul degeaba."""
    id_cerere = _cerere_evaluata(client)
    depozit.notificari_scrise.clear()

    client.post(
        "/api/v1/credite/cereri/" + id_cerere + "/mesaje",
        json={"text": "Am o intrebare."},
    )

    assert depozit.notificari_scrise == []


def test_bulina_numara_doar_mesajele_bancii_necitite(client, depozit: DepozitFals) -> None:
    """Sursa bulinei e marcajul de pe mesaje, nu notificarile.

    Altfel "marcheaza tot ca citit" din clopotel ar stinge si bulina din credite,
    desi omul n-a deschis firul.
    """
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "notifica", "Primul.")
    _decizie(client, id_cerere, "notifica", "Al doilea.")

    cereri = client.get("/api/v1/credite/cereri").json()
    cerere = next(c for c in cereri if c["id"] == id_cerere)
    assert cerere["mesaje_necitite"] == 2

    # Raspunsul propriu nu se numara: nu ai ce citi din ce ai scris tu.
    client.post("/api/v1/credite/cereri/" + id_cerere + "/mesaje", json={"text": "Am inteles."})
    cereri = client.get("/api/v1/credite/cereri").json()
    assert next(c for c in cereri if c["id"] == id_cerere)["mesaje_necitite"] == 2


def test_deschiderea_firului_stinge_bulina(client, depozit: DepozitFals) -> None:
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "notifica", "Ceva de citit.")

    raspuns = client.post("/api/v1/credite/cereri/" + id_cerere + "/mesaje/citite")
    assert raspuns.status_code == 204, raspuns.text

    cereri = client.get("/api/v1/credite/cereri").json()
    assert next(c for c in cereri if c["id"] == id_cerere)["mesaje_necitite"] == 0


def test_analistul_raspunde_in_fir_si_primeste_inapoi_mesajul(
    client, depozit: DepozitFals
) -> None:
    """Ruta libera a analistului, cea fara decizie in spate.

    Exista fiindca `/decizie` intoarce starea dosarului, iar aici nu se schimba
    nicio stare — se raspunde. Regresie: `_scrie_mesaj` intorcea doar cererea,
    iar ruta construia `MesajResponse` din campuri inexistente. Mesajul chiar se
    scria in baza, dar analistul vedea 500 si retrimitea, deci firul se umplea
    de duplicate. De-asta testul verifica **si** raspunsul, **si** ca in fir a
    ramas exact un mesaj.
    """
    id_cerere = _cerere_evaluata(client)

    raspuns = client.post(
        "/api/v1/admin/credite/cereri/" + id_cerere + "/mesaje",
        json={"text": "Adeverinta e in regula, mai verificam vechimea."},
    )

    assert raspuns.status_code == 201, raspuns.text
    corp = raspuns.json()
    assert corp["autor"] == "analist"
    assert corp["text"] == "Adeverinta e in regula, mai verificam vechimea."
    assert corp["id"] and corp["creat_la"]
    assert corp["citit_de_client_la"] is None

    fir = _fir(client, id_cerere)
    assert [m["text"] for m in fir] == ["Adeverinta e in regula, mai verificam vechimea."]


def test_confirmarea_nu_poate_sterge_o_oferta_emisa(client, depozit: DepozitFals) -> None:
    """Regresie: `oferta` nu e in STATUSURI_FINALE, deci trecea de garda.

    Confirmarea readuce cererea in 'in_analiza' si reevalueaza — adica stergea
    tacit un angajament luat fata de client, exact ce interzice `evalueaza`.
    """
    id_cerere = _cerere_evaluata(client)
    id_document = _incarca(client, id_cerere)["id"]
    assert _decizie(client, id_cerere, "aproba").json()["status"] == "oferta"

    raspuns = client.post(
        "/api/v1/admin/credite/documente/" + id_document + "/confirma",
        json={"venit_confirmat": "9400"},
    )

    assert raspuns.status_code == 422, raspuns.text
    assert "retrage" in raspuns.json()["error"]["message"].lower()

    dosar = client.get("/api/v1/admin/credite/cereri/" + id_cerere).json()
    assert dosar["cerere"]["status"] == "oferta"
    assert dosar["cerere"]["rata_lunara"] is not None


def test_retragerea_ofertei_aduce_dosarul_inapoi_si_spune_de_ce(
    client, depozit: DepozitFals
) -> None:
    """Singura cale prin care banca isi poate lua inapoi o oferta.

    Campurile ofertei se golesc, nu doar statusul: lasate acolo, ecranul ar
    arata o rata pentru ceva ce nu mai exista.
    """
    id_cerere = _cerere_evaluata(client)
    assert _decizie(client, id_cerere, "aproba").json()["status"] == "oferta"

    raspuns = _decizie(
        client, id_cerere, "retrage_oferta", "Am primit date noi despre angajator."
    )

    assert raspuns.status_code == 200, raspuns.text
    corp = raspuns.json()
    assert corp["status"] == "analiza_manuala"
    assert corp["rata_lunara"] is None
    assert corp["oferta_expira_la"] is None

    # Clientul afla de ce, si in fir, si prin notificare.
    assert _fir(client, id_cerere)[-1]["text"] == "Am primit date noi despre angajator."
    assert depozit.notificari_scrise[-1]["titlu"] == "Oferta de credit a fost retrasa"


def test_retragerea_cere_un_motiv_si_o_oferta(client, depozit: DepozitFals) -> None:
    id_cerere = _cerere_evaluata(client)

    # Fara oferta emisa nu e nimic de retras: starea gresita e OperatiuneRefuzata,
    # deci 422 cu cod `CREDIT_STARE_INVALIDA` (nu 400 — vezi handler-ul din core/errors).
    refuz = _decizie(client, id_cerere, "retrage_oferta", "Orice.")
    assert refuz.status_code == 422, refuz.text
    assert refuz.json()["error"]["code"] == "CREDIT_STARE_INVALIDA"

    _decizie(client, id_cerere, "aproba")
    # Cu oferta, dar fara motiv: clientul ar ramane cu oferta disparuta si zero
    # explicatii. Aici opreste validarea de schema, inainte sa ajunga la serviciu.
    assert _decizie(client, id_cerere, "retrage_oferta", "   ").status_code == 422


def test_clientul_isi_poate_retrage_cererea(client, depozit: DepozitFals) -> None:
    """`anulata` era status fantoma: nicio ruta nu-l producea.

    Inchiderea completeaza `finalizat_la`, deci porneste retentia documentelor —
    pana acum un dosar abandonat isi tinea adeverinta in bucket la nesfarsit.
    """
    id_cerere = _cerere_evaluata(client)

    raspuns = client.post("/api/v1/credite/cereri/" + id_cerere + "/anuleaza")

    assert raspuns.status_code == 200, raspuns.text
    assert raspuns.json()["status"] == "anulata"

    # A doua oara nu mai are ce retrage.
    assert client.post("/api/v1/credite/cereri/" + id_cerere + "/anuleaza").status_code == 422


def test_o_oferta_nu_se_anuleaza_ci_expira(client, depozit: DepozitFals) -> None:
    """Acolo omul are ceva de semnat; ignorarea duce singura la 'expirata'."""
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "aproba")

    assert client.post("/api/v1/credite/cereri/" + id_cerere + "/anuleaza").status_code == 422


def test_oferta_trecuta_de_termen_devine_expirata_la_citire(
    client, depozit: DepozitFals
) -> None:
    """Fara maturarea lenesa, ecranul arata „Semneaza" pentru ceva ce banca nu
    mai onoreaza, iar refuzul venea abia dupa apasare (din RPC)."""
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "aproba")

    depozit.cereri[id_cerere]["oferta_expira_la"] = (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).isoformat()

    cereri = client.get("/api/v1/credite/cereri").json()
    assert next(c for c in cereri if c["id"] == id_cerere)["status"] == "expirata"


def test_decizia_ajunge_la_client_nu_doar_in_baza(client, depozit: DepozitFals) -> None:
    """Motivul se scria doar in `cerere.explicatie`, iar ecranul clientului nu
    randeaza cererile respinse — deci respingerea nu ajungea nicaieri."""
    id_cerere = _cerere_evaluata(client)

    _decizie(client, id_cerere, "respinge", "Gradul de indatorare depaseste pragul.")

    fir = _fir(client, id_cerere)
    assert fir[-1]["autor"] == "analist"
    assert "indatorare" in fir[-1]["text"]
    assert depozit.notificari_scrise[-1]["titlu"] == "Cererea de credit nu a fost aprobata"
    assert depozit.notificari_scrise[-1]["tip"] == "atentionare"


def test_analistul_poate_raspunde_si_pe_o_oferta(client, depozit: DepozitFals) -> None:
    """Dead-end real: clientul putea scrie pe oferta, analistul nu putea raspunde.

    Un raspuns nu e o decizie si nu atinge angajamentul — dar o actiune care
    schimba starea (`cere_documente`) ramane refuzata acolo.
    """
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "aproba")

    client.post(
        "/api/v1/credite/cereri/" + id_cerere + "/mesaje",
        json={"text": "Pot semna saptamana viitoare?"},
    )

    raspuns = client.post(
        "/api/v1/admin/credite/cereri/" + id_cerere + "/mesaje",
        json={"text": "Da, oferta e valabila 7 zile."},
    )
    assert raspuns.status_code == 201, raspuns.text

    # Dar starea nu se schimba de aici.
    assert _decizie(client, id_cerere, "cere_documente", "Mai vrem ceva.").status_code == 422
    assert client.get("/api/v1/credite/cereri").json()[0]["status"] == "oferta"


def test_incarcarea_proprie_nu_aprinde_bulina_clientului(
    client, depozit: DepozitFals
) -> None:
    """Necitit inseamna `autor='analist'`, nu „tot ce nu e al clientului".

    Mesajul de document e semnat `sistem`, dar il produce fapta clientului — o
    bulina pentru propria incarcare n-are ce sa-i spuna.
    """
    id_cerere = _cerere_evaluata(client)
    _incarca(client, id_cerere)

    cereri = client.get("/api/v1/credite/cereri").json()
    assert next(c for c in cereri if c["id"] == id_cerere)["mesaje_necitite"] == 0


def test_banca_vede_ca_a_primit_un_mesaj(client, depozit: DepozitFals) -> None:
    """Necititul era unidirectional: clientul vedea bulina, banca nu.

    Un dosar in care clientul a scris „nu inteleg ce vreti" statea in coada pana
    se uita cineva din intamplare in el.
    """
    id_cerere = _cerere_evaluata(client)
    # `notifica`, nu `cere_documente`: al doilea muta dosarul in
    # 'asteapta_documente', iar coada `analiza-manuala` nu-l mai contine.
    _decizie(client, id_cerere, "notifica", "Verificam vechimea.")

    client.post(
        "/api/v1/credite/cereri/" + id_cerere + "/mesaje",
        json={"text": "Nu inteleg ce fel de adeverinta."},
    )

    coada = client.get("/api/v1/admin/credite/analiza-manuala").json()
    assert next(c for c in coada if c["id"] == id_cerere)["mesaje_necitite"] == 1

    # Deschiderea dosarului o stinge: firul vine in acelasi raspuns.
    client.get("/api/v1/admin/credite/cereri/" + id_cerere)
    coada = client.get("/api/v1/admin/credite/analiza-manuala").json()
    assert next(c for c in coada if c["id"] == id_cerere)["mesaje_necitite"] == 0


def test_cele_doua_buline_sunt_independente(client, depozit: DepozitFals) -> None:
    """Doua coloane, nu una cu rol dublu: altfel deschiderea firului de catre
    analist ar stinge si bulina clientului."""
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "notifica", "Ceva de citit.")
    client.post("/api/v1/credite/cereri/" + id_cerere + "/mesaje", json={"text": "Ok."})

    client.get("/api/v1/admin/credite/cereri/" + id_cerere)

    cereri = client.get("/api/v1/credite/cereri").json()
    assert next(c for c in cereri if c["id"] == id_cerere)["mesaje_necitite"] == 1


def test_jurnalul_cererii_ajunge_in_dosar(client, depozit: DepozitFals) -> None:
    """`credit_evenimente` se scria din 16 locuri si nu-l citea nicio ruta."""
    id_cerere = _cerere_evaluata(client)
    _decizie(client, id_cerere, "notifica", "Verificam vechimea.")

    dosar = client.get("/api/v1/admin/credite/cereri/" + id_cerere).json()

    tipuri = [e["tip"] for e in dosar["evenimente"]]
    assert "client_notificat" in tipuri
    # Cronologic crescator: jurnalul se citeste ca o poveste, nu ca un feed.
    momente = [e["creat_la"] for e in dosar["evenimente"]]
    assert momente == sorted(momente)
    assert all(e["actor"] for e in dosar["evenimente"])

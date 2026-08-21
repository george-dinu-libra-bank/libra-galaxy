"""Fluxul de creditare, prin HTTP, cu un depozit fals in memorie.

De ce prin `TestClient(app)` si nu direct pe serviciu: bug-ul care a scapat in
productie nu era in logica, ci in stratul de rute — `vars()` pe un dataclass cu
`slots=True` arunca TypeError, iar API-ul raspundea 500 desi serviciul calcula
corect. Un test care apeleaza doar `CreditService` trecea vesel. Testele de aici
merg pe acelasi drum ca browserul: request -> ruta -> serviciu -> response_model.

Depozitul fals imita semantica RPC-urilor din 0010 (acordare, incasare de rate,
rambursare) suficient cat sa exerseze serviciul. Nu inlocuieste verificarea live
din `app/scripts/verifica_flux_credit.py` — aceea e singura care dovedeste ca SQL-ul
chiar face ce credem. Asta ruleaza in CI, fara baza de date.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import UserContext, get_credit_service, get_current_user
from app.main import app
from app.services.credit_service import CreditService

ID_USER = uuid.UUID("11111111-1111-4111-8111-111111111111")
ID_CONT = "22222222-2222-4222-8222-222222222222"
ID_PRODUS = "33333333-3333-4333-8333-333333333333"

# Nascut 1990-05-15: are 21-70 de ani la orice data plauzibila de rulare a testului.
CNP = "1900515123456"

PRODUS = {
    "id": ID_PRODUS, "slug": "galaxy-flex-personal", "nume": "Galaxy Flex Personal",
    "dobanda_anuala": "0.0990", "suma_min": "5000.00", "suma_max": "150000.00",
    "luni_min": 6, "luni_max": 60, "varsta_min": 21, "varsta_max": 70,
    "venit_net_minim": "3000.00", "vechime_angajator_luni": 6, "vechime_venituri_luni": 12,
}


class DepozitFals:
    """Imita CreditRepository, inclusiv semantica celor trei RPC-uri."""

    def __init__(
        self,
        *,
        salariu: float = 8500.0,
        luni_salariu: int = 12,
        verificare: str = "verified",
        sold_cont: float = 20000.0,
        expuneri: list[dict] | None = None,
    ) -> None:
        self.salariu = salariu
        self.luni_salariu = luni_salariu
        self.verificare = verificare
        self.sold_cont = sold_cont
        self._expuneri = expuneri or []

        self.cereri: dict[str, dict] = {}
        self.credite: dict[str, dict] = {}
        # Numit cu underscore: `rate` e si metoda, iar atributul ar umbri-o.
        self._rate: dict[str, list[dict]] = {}
        self.verificari_scrise: list[dict] = []
        self.evenimente: list[dict] = []

    # -- citiri -------------------------------------------------------------

    async def produs(self, slug: str) -> dict | None:
        return PRODUS if slug == "galaxy-flex-personal" else None

    async def profil(self, user_id) -> dict:
        return {
            "id": str(user_id), "nume": "Test Testescu", "cnp": CNP,
            "verification_status": self.verificare,
            "creat_la": (datetime.now(timezone.utc) - timedelta(days=730)).isoformat(),
        }

    async def conturi(self, user_id) -> list[dict]:
        return [{
            "id": ID_CONT, "nume": "Cont curent", "iban": "RO49AAAA1B31007593840000",
            "sold": self.sold_cont, "valuta": "RON",
            "creat_la": datetime.now(timezone.utc).isoformat(),
        }]

    async def tranzactii_pentru_venit(self, user_id, luni: int = 14) -> list[dict]:
        """Salariu lunar constant — tiparul pe care detectorul trebuie sa il gaseasca."""
        acum = datetime.now(timezone.utc)
        return [
            {
                "id": str(uuid.uuid4()), "suma": self.salariu, "valuta": "RON",
                "descriere": "Salariu",
                "creat_la": (acum - timedelta(days=30 * (indice + 1))).isoformat(),
                "id_user_send": None, "id_user_recieve": str(user_id),
            }
            for indice in range(self.luni_salariu)
        ]

    async def expuneri_birou(self, cnp: str) -> list[dict]:
        return self._expuneri

    async def rate_lunare_credite_active(self, user_id) -> float:
        return sum(
            float(credit["rata_lunara"]) for credit in self.credite.values()
            if credit["status"] in ("activ", "restant")
        )

    # -- cereri -------------------------------------------------------------

    async def creeaza_cerere(self, campuri: dict[str, Any]) -> dict:
        rand = {
            "id": str(uuid.uuid4()), "creat_la": datetime.now(timezone.utc).isoformat(),
            "venit_folosit": None, "obligatii_folosite": None, "dti": None, "scor": None,
            "motive": [], "explicatie": None, "rata_lunara": None, "dae": None,
            "oferta_expira_la": None, **campuri,
        }
        self.cereri[rand["id"]] = rand
        return rand

    async def cerere(self, id_cerere) -> dict | None:
        return self.cereri.get(str(id_cerere))

    async def cereri_utilizator(self, user_id) -> list[dict]:
        return [c for c in self.cereri.values() if c["id_user"] == str(user_id)]

    async def actualizeaza_cerere(self, id_cerere, campuri: dict[str, Any]) -> dict:
        self.cereri[str(id_cerere)].update(campuri)
        return self.cereri[str(id_cerere)]

    async def salveaza_verificare(self, campuri: dict[str, Any]) -> dict:
        self.verificari_scrise.append(campuri)
        return campuri

    async def verificari(self, id_cerere) -> list[dict]:
        return [
            {"venit_constatat": None, "obligatii_constatate": None, "incredere": 0, **v}
            for v in self.verificari_scrise
            if v["id_cerere"] == str(id_cerere)
        ]

    async def salveaza_document(self, campuri: dict[str, Any]) -> dict:
        return campuri

    async def eveniment(self, campuri: dict[str, Any]) -> None:
        self.evenimente.append(campuri)

    # -- credite ------------------------------------------------------------

    async def credit(self, id_credit) -> dict | None:
        return self.credite.get(str(id_credit))

    async def credite_utilizator(self, user_id) -> list[dict]:
        return [k for k in self.credite.values() if k["id_user"] == str(user_id)]

    async def rate(self, id_credit) -> list[dict]:
        return self._rate.get(str(id_credit), [])

    # -- operatiuni (semantica RPC-urilor din 0010) -------------------------

    async def acorda(self, id_cerere, id_cont, rata_lunara, dae, grafic, semnatura) -> dict:
        cerere = self.cereri[str(id_cerere)]
        if cerere["status"] != "oferta":
            raise RuntimeError("CERERE_IN_STARE_GRESITA")

        # Aceeasi verificare ca in SQL: graficul trebuie sa insumeze exact creditul.
        suma = float(cerere["suma_ceruta"])
        if round(sum(float(r["principal"]) for r in grafic), 2) != round(suma, 2):
            raise RuntimeError("GRAFIC_INVALID")

        id_credit = str(uuid.uuid4())
        self.credite[id_credit] = {
            "id": id_credit, "id_cerere": str(id_cerere), "id_user": cerere["id_user"],
            "id_cont_creditare": str(id_cont), "principal": suma,
            "dobanda_anuala": PRODUS["dobanda_anuala"], "luni": cerere["luni"],
            "rata_lunara": rata_lunara, "dae": dae, "sold_ramas": suma,
            "data_acordarii": date.today().isoformat(),
            "semnat_la": datetime.now(timezone.utc).isoformat(),
            "status": "activ", "inchis_la": None,
            "creat_la": datetime.now(timezone.utc).isoformat(),
        }
        self._rate[id_credit] = [
            {
                "id": str(uuid.uuid4()), "numar_rata": r["numar"], "scadenta": r["scadenta"],
                "principal_rata": r["principal"], "dobanda_rata": r["dobanda"],
                "rata_totala": r["total"], "sold_dupa": r["sold_dupa"],
                "status": "programata", "platita_la": None, "id_tranzactie": None,
            }
            for r in grafic
        ]
        self.sold_cont += suma
        cerere["status"] = "acceptata"

        return {
            "id_credit": id_credit, "id_tranzactie": str(uuid.uuid4()), "principal": suma,
            "rata_lunara": rata_lunara, "luni": cerere["luni"], "sold_cont_nou": self.sold_cont,
            "prima_scadenta": grafic[0]["scadenta"],
        }

    async def incaseaza_rate(self, id_credit, pana_la=None) -> dict:
        credit = self.credite[str(id_credit)]
        if credit["status"] in ("inchis", "rambursat_anticipat"):
            return {"rate_platite": 0}

        limita = pana_la or date.today()
        platite = 0
        for rata in self._rate[str(id_credit)]:
            if rata["status"] not in ("programata", "restanta"):
                continue
            if date.fromisoformat(rata["scadenta"]) > limita:
                continue
            if self.sold_cont < float(rata["rata_totala"]):
                rata["status"] = "restanta"
                credit["status"] = "restant"
                break
            self.sold_cont -= float(rata["rata_totala"])
            rata["status"] = "platita"
            rata["platita_la"] = datetime.now(timezone.utc).isoformat()
            credit["sold_ramas"] = float(rata["sold_dupa"])
            platite += 1

        if all(r["status"] == "platita" for r in self._rate[str(id_credit)]):
            credit["status"] = "inchis"
            credit["sold_ramas"] = 0.0
            credit["inchis_la"] = datetime.now(timezone.utc).isoformat()

        return {"rate_platite": platite, "sold_ramas": credit["sold_ramas"]}

    async def ramburseaza_anticipat(
        self, id_credit, principal_platit, dobanda_acumulata=0.0, grafic_nou=None
    ) -> dict:
        credit = self.credite[str(id_credit)]
        integral = round(principal_platit, 2) >= round(float(credit["sold_ramas"]), 2)
        total = principal_platit + dobanda_acumulata

        if self.sold_cont < total:
            raise RuntimeError("FONDURI_INSUFICIENTE")

        self.sold_cont -= total
        for rata in self._rate[str(id_credit)]:
            if rata["status"] in ("programata", "restanta"):
                rata["status"] = "anulata"

        if integral:
            credit["sold_ramas"] = 0.0
            credit["status"] = "rambursat_anticipat"
            credit["inchis_la"] = datetime.now(timezone.utc).isoformat()
        else:
            credit["sold_ramas"] = float(credit["sold_ramas"]) - principal_platit
            credit["status"] = "activ"

        return {
            "id_tranzactie": str(uuid.uuid4()), "principal_platit": principal_platit,
            "dobanda_platita": dobanda_acumulata, "total_platit": total,
            "sold_ramas": credit["sold_ramas"], "status": credit["status"],
            "sold_cont": self.sold_cont,
        }


@pytest.fixture
def depozit() -> DepozitFals:
    return DepozitFals()


@pytest.fixture
def client(depozit: DepozitFals):
    app.dependency_overrides[get_current_user] = lambda: UserContext(
        user_id=ID_USER, access_token="test"
    )
    app.dependency_overrides[get_credit_service] = lambda: CreditService(depozit)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _cerere(client, suma="30000", luni=36, venit="8500") -> str:
    raspuns = client.post("/api/v1/credite/cereri", json={
        "suma": suma, "luni": luni, "venit_declarat": venit,
        "angajator": "ACME SRL", "vechime_angajator_luni": 24,
        "obligatii_declarate": "0", "consimtamant": True,
    })
    assert raspuns.status_code == 201, raspuns.text
    return raspuns.json()["id"]


# ---------------------------------------------------------------------------
# Rutele raspund, si raspund cu ce trebuie
# ---------------------------------------------------------------------------


def test_produsul_se_citeste_din_catalog(client) -> None:
    raspuns = client.get("/api/v1/credite/produs")

    assert raspuns.status_code == 200, raspuns.text
    assert raspuns.json()["slug"] == "galaxy-flex-personal"


def test_simularea_raspunde_cu_grafic_complet(client) -> None:
    """Regresie: ruta folosea vars() pe un dataclass cu slots=True si dadea 500."""
    raspuns = client.post("/api/v1/credite/simulare", json={"suma": "30000", "luni": 36})

    assert raspuns.status_code == 200, raspuns.text
    corp = raspuns.json()
    assert len(corp["grafic"]) == 36
    assert float(corp["rata_lunara"]) > 0
    assert float(corp["dae"]) > float(corp["dobanda_anuala"])
    assert float(corp["grafic"][-1]["sold_dupa"]) == 0


def test_evaluarea_raspunde_cu_decizie_motivata(client) -> None:
    """Aceeasi regresie, pe cealalta ruta care serializa un dataclass cu slots."""
    id_cerere = _cerere(client)
    raspuns = client.post(f"/api/v1/credite/cereri/{id_cerere}/evalueaza")

    assert raspuns.status_code == 200, raspuns.text
    corp = raspuns.json()
    assert corp["decizie"] in ("aprobat", "analiza_manuala", "respins")
    assert corp["explicatie"]
    assert len(corp["factori"]) == 6


def test_cererea_fara_consimtamant_e_refuzata(client) -> None:
    raspuns = client.post("/api/v1/credite/cereri", json={
        "suma": "30000", "luni": 36, "venit_declarat": "8500",
        "angajator": "ACME SRL", "vechime_angajator_luni": 24,
        "obligatii_declarate": "0", "consimtamant": False,
    })

    assert raspuns.status_code == 422
    assert raspuns.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Deciziile
# ---------------------------------------------------------------------------


def test_venitul_din_tranzactii_bate_declaratia(client, depozit: DepozitFals) -> None:
    """Clientul declara 20.000, banca gaseste 8.500 in cont. Castiga contul."""
    id_cerere = _cerere(client, venit="20000")
    client.post(f"/api/v1/credite/cereri/{id_cerere}/evalueaza")

    folosit = depozit.cereri[id_cerere]["venit_folosit"]
    assert float(folosit) == pytest.approx(8500.0)

    surse = {v["sursa"] for v in depozit.verificari_scrise}
    assert surse == {"declarat", "tranzactii", "birou_credit"}


def test_venitul_sub_minim_respinge_cu_motiv(depozit: DepozitFals) -> None:
    depozit.salariu = 2400.0
    app.dependency_overrides[get_current_user] = lambda: UserContext(ID_USER, "t")
    app.dependency_overrides[get_credit_service] = lambda: CreditService(depozit)
    try:
        client = TestClient(app)
        id_cerere = _cerere(client, suma="20000", venit="2400")
        corp = client.post(f"/api/v1/credite/cereri/{id_cerere}/evalueaza").json()

        assert corp["decizie"] == "respins"
        assert "venit_sub_minim" in {motiv["cod"] for motiv in corp["motive"]}
    finally:
        app.dependency_overrides.clear()


def test_identitatea_neverificata_blocheaza_creditarea(depozit: DepozitFals) -> None:
    """KYC-ul existent (migrarea 0007) e poarta de creditare, nu un ecran decorativ."""
    depozit.verificare = "pending"
    app.dependency_overrides[get_current_user] = lambda: UserContext(ID_USER, "t")
    app.dependency_overrides[get_credit_service] = lambda: CreditService(depozit)
    try:
        client = TestClient(app)
        id_cerere = _cerere(client)
        corp = client.post(f"/api/v1/credite/cereri/{id_cerere}/evalueaza").json()

        assert corp["decizie"] == "respins"
        assert "identitate_neverificata" in {motiv["cod"] for motiv in corp["motive"]}
    finally:
        app.dependency_overrides.clear()


def test_obligatiile_de_la_alte_banci_intra_in_dti(depozit: DepozitFals) -> None:
    depozit._expuneri = [{"banca": "Alta Banca", "rata_lunara": "2600", "sold": "60000"}]
    app.dependency_overrides[get_current_user] = lambda: UserContext(ID_USER, "t")
    app.dependency_overrides[get_credit_service] = lambda: CreditService(depozit)
    try:
        client = TestClient(app)
        id_cerere = _cerere(client)
        corp = client.post(f"/api/v1/credite/cereri/{id_cerere}/evalueaza").json()

        assert corp["decizie"] == "respins"
        assert "grad_indatorare_depasit" in {motiv["cod"] for motiv in corp["motive"]}
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Ciclul complet
# ---------------------------------------------------------------------------


def test_fluxul_complet_pana_la_credit_stins(client, depozit: DepozitFals) -> None:
    """Cerere -> aprobare -> acordare -> rate -> rambursare -> inchidere."""
    sold_initial = depozit.sold_cont

    id_cerere = _cerere(client)
    decizie = client.post(f"/api/v1/credite/cereri/{id_cerere}/evalueaza").json()
    assert decizie["decizie"] == "aprobat", decizie

    acordare = client.post(
        f"/api/v1/credite/cereri/{id_cerere}/accepta", json={"id_cont": ID_CONT}
    )
    assert acordare.status_code == 200, acordare.text
    id_credit = acordare.json()["id_credit"]

    # Banii au intrat efectiv in cont.
    assert depozit.sold_cont == pytest.approx(sold_initial + 30000.0)

    lista = client.get("/api/v1/credite").json()
    assert len(lista) == 1 and lista[0]["status"] == "activ"

    # Trei rate, prin avansul de timp — altfel ar trebui asteptate trei luni.
    detaliu = client.post(f"/api/v1/credite/{id_credit}/avanseaza-timp?luni=3")
    assert detaliu.status_code == 200, detaliu.text
    assert detaliu.json()["rate_platite"] == 3

    calcul = client.get(f"/api/v1/credite/{id_credit}/rambursare").json()
    assert float(calcul["sold"]) > 0
    assert float(calcul["economie_dobanda"]) > 0

    stingere = client.post(f"/api/v1/credite/{id_credit}/rambursare", json={"suma": None})
    assert stingere.status_code == 200, stingere.text
    assert stingere.json()["status"] == "rambursat_anticipat"
    assert float(stingere.json()["sold_ramas"]) == 0

    # Creditul stins nu mai accepta o a doua rambursare.
    assert client.get(f"/api/v1/credite/{id_credit}/rambursare").status_code == 422


def test_o_cerere_cu_oferta_nu_se_reevalueaza(client) -> None:
    """Oferta e un angajament, nu o parere care se poate schimba la refresh."""
    id_cerere = _cerere(client)
    client.post(f"/api/v1/credite/cereri/{id_cerere}/evalueaza")

    din_nou = client.post(f"/api/v1/credite/cereri/{id_cerere}/evalueaza")

    assert din_nou.status_code == 422
    assert din_nou.json()["error"]["code"] == "CREDIT_STARE_INVALIDA"


def test_cererea_altcuiva_nu_se_vede(client, depozit: DepozitFals) -> None:
    strain = uuid.uuid4()
    depozit.cereri[str(strain)] = {
        "id": str(strain), "id_user": str(uuid.uuid4()), "status": "oferta",
        "suma_ceruta": "30000", "luni": 36,
        "creat_la": datetime.now(timezone.utc).isoformat(),
    }

    raspuns = client.get(f"/api/v1/credite/cereri/{strain}")

    assert raspuns.status_code == 404
    assert raspuns.json()["error"]["code"] == "CREDIT_NOT_FOUND"


def test_ratele_se_incaseaza_o_singura_data(client, depozit: DepozitFals) -> None:
    """Idempotenta: doua apeluri identice nu iau banii de doua ori."""
    id_cerere = _cerere(client)
    client.post(f"/api/v1/credite/cereri/{id_cerere}/evalueaza")
    id_credit = client.post(
        f"/api/v1/credite/cereri/{id_cerere}/accepta", json={"id_cont": ID_CONT}
    ).json()["id_credit"]

    client.post(f"/api/v1/credite/{id_credit}/avanseaza-timp?luni=3")
    dupa_prima = depozit.sold_cont

    client.post(f"/api/v1/credite/{id_credit}/avanseaza-timp?luni=3")

    assert depozit.sold_cont == dupa_prima

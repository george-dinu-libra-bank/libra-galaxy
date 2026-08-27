"""Cererea de inchidere a contului: cine o poate depune si ce o blocheaza.

Regula de fond: **cerere, nu stergere pe loc.** O banca nu inchide un client cat
timp are un credit in derulare sau bani in cont, iar stergerea e ireversibila,
deci trece pe la un om. Aceleasi teste apara si formularea mesajelor — un
„nu se poate" gol e exact motivul pentru care oamenii suna la call center.
"""

from __future__ import annotations

import pytest

from app.core.errors import ResourceNotFoundError, ValidationError
from app.services.profile_service import ProfileService

ID_USER = "5f801e91-0fd4-462f-a78c-61ec1d6dc12b"


class _DepozitFals:
    def __init__(self, *, credite: int = 0, conturi=None, deschisa=None) -> None:
        self._credite = credite
        self._conturi = conturi or []
        self.deschisa = deschisa
        self.create: list[dict] = []
        self.retrase: list[str] = []

    async def numara_credite_in_derulare(self, user_id):
        return self._credite

    async def conturi_cu_sold(self, user_id):
        return self._conturi

    async def cerere_stergere_deschisa(self, user_id):
        return self.deschisa

    async def creeaza_cerere_stergere(self, user_id, motiv):
        rand = {
            "id": "11111111-1111-4111-8111-111111111111",
            "status": "in_asteptare",
            "motiv": motiv,
            "creat_la": "2026-08-26T10:00:00+00:00",
        }
        self.create.append(rand)
        return rand

    async def retrage_cerere_stergere(self, user_id, id_cerere):
        if self.deschisa is None:
            return None
        self.retrase.append(id_cerere)
        return {**self.deschisa, "status": "retrasa"}


def _serviciu(**kwargs) -> tuple[ProfileService, _DepozitFals]:
    depozit = _DepozitFals(**kwargs)
    return ProfileService(depozit), depozit


async def test_contul_curat_poate_fi_inchis() -> None:
    serviciu, depozit = _serviciu()

    cerere = await serviciu.cere_stergere(ID_USER, "Ma mut la alta banca")

    assert cerere.status == "in_asteptare"
    assert depozit.create[0]["motiv"] == "Ma mut la alta banca"


async def test_motivul_e_optional() -> None:
    """Nu conditionam plecarea unui client de o explicatie."""
    serviciu, _ = _serviciu()

    cerere = await serviciu.cere_stergere(ID_USER, None)

    assert cerere.status == "in_asteptare"


async def test_creditul_in_derulare_nu_opreste_cererea_dar_se_spune() -> None:
    """Poarta adevarata sta la stergere (public.sterge_client), nu la depunere.

    Cine vrea sa plece n-are de trecut un examen ca sa poata cere: i se spune ce
    mai are de facut, si atat.
    """
    serviciu, _ = _serviciu(credite=1)

    cerere = await serviciu.cere_stergere(ID_USER, None)
    stare = await serviciu.stare_stergere(ID_USER)

    assert cerere.status == "in_asteptare"
    assert "credit in derulare" in stare.motive_blocare[0]


async def test_pluralul_e_corect_la_mai_multe_credite() -> None:
    """Detaliu mic, dar textul ajunge in fata omului: „Ai 3 credit in derulare"
    arata ca un mesaj generat de o masina care nu s-a uitat la ce scrie."""
    serviciu, _ = _serviciu(credite=3)

    stare = await serviciu.stare_stergere(ID_USER)

    assert "Ai 3 credite in derulare" in stare.motive_blocare[0]


async def test_banii_ramasi_se_spun_dar_nu_opresc_cererea() -> None:
    serviciu, _ = _serviciu(
        conturi=[{"id": "1", "nume": "Cont curent", "sold": "1250.00", "valuta": "RON"}]
    )

    cerere = await serviciu.cere_stergere(ID_USER, None)
    stare = await serviciu.stare_stergere(ID_USER)

    assert cerere.status == "in_asteptare"
    assert "Cont curent" in stare.motive_blocare[0]
    assert "1250.00" in stare.motive_blocare[0]


async def test_soldul_negativ_blocheaza_cu_alt_mesaj() -> None:
    """Un sold negativ nu inseamna „mai ai bani", ci „datorezi" — si trebuie
    spus asa, altfel omul cauta banii pe care ii are de dat."""
    serviciu, _ = _serviciu(
        conturi=[{"id": "1", "nume": "Cont curent", "sold": "-40.00", "valuta": "RON"}]
    )

    stare = await serviciu.stare_stergere(ID_USER)

    assert "sold negativ" in stare.motive_blocare[0]
    # Se poate cere; ce nu se poate inca e stergerea efectiva.
    assert stare.poate_cere is True


async def test_a_doua_cerere_e_refuzata() -> None:
    deschisa = {
        "id": "22222222-2222-4222-8222-222222222222",
        "status": "in_asteptare",
        "motiv": None,
        "creat_la": "2026-08-26T10:00:00+00:00",
    }
    serviciu, _ = _serviciu(deschisa=deschisa)

    with pytest.raises(ValidationError) as eroare:
        await serviciu.cere_stergere(ID_USER, None)

    assert "deja o cerere" in str(eroare.value)


async def test_starea_spune_ce_poate_face_omul_inainte_sa_apese() -> None:
    serviciu, _ = _serviciu()

    stare = await serviciu.stare_stergere(ID_USER)

    assert stare.poate_cere is True
    assert stare.motive_blocare == []
    assert stare.cerere is None


async def test_clientul_isi_poate_retrage_cererea() -> None:
    deschisa = {
        "id": "33333333-3333-4333-8333-333333333333",
        "status": "in_asteptare",
        "motiv": None,
        "creat_la": "2026-08-26T10:00:00+00:00",
    }
    serviciu, _ = _serviciu(deschisa=deschisa)

    cerere = await serviciu.retrage_stergere(ID_USER, deschisa["id"])

    assert cerere.status == "retrasa"


async def test_retragerea_unei_cereri_inexistente_da_404() -> None:
    serviciu, _ = _serviciu()

    with pytest.raises(ResourceNotFoundError):
        await serviciu.retrage_stergere(ID_USER, "44444444-4444-4444-8444-444444444444")

"""Hotararea administratorului asupra unui cont: istoric, blocare, notificare."""

from uuid import uuid4

import pytest

from app.core.errors import ResourceNotFoundError, ValidationError
from app.services.analiza_cont_service import AnalizaContService

ADMIN = uuid4()
CLIENT = uuid4()


class _AnalizeFalse:
    def __init__(self, conturi: list[dict] | None = None) -> None:
        self.conturi_rand = conturi if conturi is not None else [
            {"id": "c1", "blocat_administrativ": False},
            {"id": "c2", "blocat_administrativ": False},
        ]
        self.analize: list[dict] = []
        self.notificari: list[dict] = []
        self.notificare_crapa = False

    async def conturi(self, _user_id):
        return self.conturi_rand

    async def schimba_blocarea(self, _user_id, blocat):
        de_schimbat = [
            c for c in self.conturi_rand if bool(c["blocat_administrativ"]) != blocat
        ]
        for c in de_schimbat:
            c["blocat_administrativ"] = blocat
        return len(de_schimbat)

    async def scrie_analiza(self, campuri):
        self.analize.append(campuri)
        return {**campuri, "creat_la": "2026-08-24T10:00:00+00:00"}

    async def scrie_notificare(self, user_id, titlu, mesaj, tip):
        if self.notificare_crapa:
            raise RuntimeError("storage indisponibil")
        rand = {"id_utilizator": str(user_id), "titlu": titlu, "mesaj": mesaj, "tip": tip}
        self.notificari.append(rand)
        return rand

    async def istoric(self, _user_id, limita=50):
        return list(reversed(self.analize))


class _ProfiluriFalse:
    def __init__(self, exista: bool = True) -> None:
        self._exista = exista

    async def profil(self, _user_id):
        return {"id": str(CLIENT), "nume": "Ion Popescu"} if self._exista else None


def _serviciu(analize=None, exista=True):
    return AnalizaContService(analize or _AnalizeFalse(), _ProfiluriFalse(exista))


# ---------------------------------------------------------------------------
# Ce se intampla cu contul
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_frauda_consemnata_nu_blocheaza_singura() -> None:
    """Verdictul si masura sunt acte diferite.

    Un administrator poate hotari ca un caz e suspect fara sa blocheze inca
    nimic — de exemplu pana verifica cineva mai departe. Nimic nu se aplica pe
    contul cuiva fara ca un om sa fi cerut acea masura anume.
    """
    analize = _AnalizeFalse()

    rezultat = await _serviciu(analize).decide(CLIENT, ADMIN, "frauda", "acte falsificate")

    assert rezultat.conturi_atinse == 0
    assert not any(c["blocat_administrativ"] for c in analize.conturi_rand)
    assert analize.notificari == []


@pytest.mark.anyio
async def test_blocarea_ceruta_anume_blocheaza_toate_conturile() -> None:
    analize = _AnalizeFalse()

    rezultat = await _serviciu(analize).decide(
        CLIENT, ADMIN, "frauda", "acte falsificate", aplica_blocarea=True
    )

    assert rezultat.conturi_atinse == 2
    assert all(c["blocat_administrativ"] for c in analize.conturi_rand)


@pytest.mark.anyio
async def test_deblocarea_ridica_blocarea() -> None:
    analize = _AnalizeFalse([{"id": "c1", "blocat_administrativ": True}])

    rezultat = await _serviciu(analize).decide(CLIENT, ADMIN, "deblocat", "clarificat")

    assert rezultat.conturi_atinse == 1
    assert not analize.conturi_rand[0]["blocat_administrativ"]


@pytest.mark.anyio
async def test_acceptarea_nu_atinge_contul() -> None:
    """Un cont verificat si gasit in regula ramane exact cum era."""
    analize = _AnalizeFalse()

    rezultat = await _serviciu(analize).decide(CLIENT, ADMIN, "acceptat", "explicat de client")

    assert rezultat.conturi_atinse == 0
    assert not any(c["blocat_administrativ"] for c in analize.conturi_rand)


@pytest.mark.anyio
async def test_un_cont_deja_blocat_nu_se_numara_de_doua_ori() -> None:
    analize = _AnalizeFalse([{"id": "c1", "blocat_administrativ": True}, {"id": "c2", "blocat_administrativ": False}])

    rezultat = await _serviciu(analize).decide(
        CLIENT, ADMIN, "frauda", None, aplica_blocarea=True
    )

    assert rezultat.conturi_atinse == 1


# ---------------------------------------------------------------------------
# Istoricul
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_decizia_intra_in_istoric_cu_observatia() -> None:
    analize = _AnalizeFalse()

    await _serviciu(analize).decide(
        CLIENT, ADMIN, "acceptat", "  am sunat clientul, confirma platile  ",
        gravitate=93, numar_semnalari=19, zile=30,
    )

    assert len(analize.analize) == 1
    rand = analize.analize[0]
    assert rand["decizie"] == "acceptat"
    assert rand["observatie"] == "am sunat clientul, confirma platile"
    assert rand["id_administrator"] == str(ADMIN)
    assert rand["gravitate"] == 93


@pytest.mark.anyio
async def test_gravitatea_se_ingheata_asa_cum_era() -> None:
    """Peste un an, pragurile pot fi altele; istoricul trebuie sa arate ce a vazut omul."""
    analize = _AnalizeFalse()

    await _serviciu(analize).decide(CLIENT, ADMIN, "frauda", None, gravitate=88, numar_semnalari=4)

    assert analize.analize[0]["gravitate"] == 88
    assert analize.analize[0]["numar_semnalari"] == 4


@pytest.mark.anyio
async def test_o_observatie_goala_ramane_goala_nu_sir_vid() -> None:
    analize = _AnalizeFalse()

    await _serviciu(analize).decide(CLIENT, ADMIN, "acceptat", "   ")

    assert analize.analize[0]["observatie"] is None


# ---------------------------------------------------------------------------
# Notificarea
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_blocarea_il_anunta_pe_client() -> None:
    analize = _AnalizeFalse()

    rezultat = await _serviciu(analize).decide(
        CLIENT, ADMIN, "frauda", None, aplica_blocarea=True
    )

    assert rezultat.notificare_trimisa
    assert analize.notificari[0]["tip"] == "blocare"


@pytest.mark.anyio
async def test_observatia_ajunge_in_notificare() -> None:
    analize = _AnalizeFalse()

    await _serviciu(analize).decide(
        CLIENT, ADMIN, "frauda", "tranzactii catre conturi noi", aplica_blocarea=True
    )

    assert "tranzactii catre conturi noi" in analize.notificari[0]["mesaj"]


@pytest.mark.anyio
async def test_acceptarea_nu_sperie_clientul_degeaba() -> None:
    analize = _AnalizeFalse()

    rezultat = await _serviciu(analize).decide(CLIENT, ADMIN, "acceptat", None)

    assert analize.notificari == []
    assert not rezultat.notificare_trimisa


@pytest.mark.anyio
async def test_o_notificare_esuata_nu_pierde_decizia() -> None:
    """Blocarea deja s-a aplicat; anularea ei ar fi mai rea decat un mesaj lipsa."""
    analize = _AnalizeFalse()
    analize.notificare_crapa = True

    rezultat = await _serviciu(analize).decide(
        CLIENT, ADMIN, "frauda", None, aplica_blocarea=True
    )

    assert not rezultat.notificare_trimisa
    assert rezultat.conturi_atinse == 2
    assert len(analize.analize) == 1


# ---------------------------------------------------------------------------
# Ce se respinge
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_o_decizie_inventata_e_respinsa() -> None:
    with pytest.raises(ValidationError):
        await _serviciu().decide(CLIENT, ADMIN, "sterge_contul", None)


@pytest.mark.anyio
async def test_un_cont_inexistent_da_404() -> None:
    with pytest.raises(ResourceNotFoundError):
        await _serviciu(exista=False).decide(CLIENT, ADMIN, "acceptat", None)


@pytest.mark.anyio
async def test_o_observatie_prea_lunga_e_respinsa() -> None:
    with pytest.raises(ValidationError):
        await _serviciu().decide(CLIENT, ADMIN, "acceptat", "x" * 2001)


@pytest.mark.anyio
async def test_contul_inexistent_e_verificat_inainte_sa_se_blocheze_ceva() -> None:
    analize = _AnalizeFalse()

    with pytest.raises(ResourceNotFoundError):
        await AnalizaContService(analize, _ProfiluriFalse(False)).decide(
            CLIENT, ADMIN, "frauda", None, aplica_blocarea=True
        )

    assert not any(c["blocat_administrativ"] for c in analize.conturi_rand)
    assert analize.analize == []

from uuid import uuid4

import pytest

from app.agents.baza import AgentIndisponibil, RezultatAgent, ruleaza_bucla
from app.agents.orchestrator import _unealta_de_delegare
from app.infrastructure.llm import CerereTool, RaspunsModel
from app.schemas.agents import ApelAgent
from app.services.analiza_service import AnalizaService
from app.tools import financiar_tools
from app.tools.unealta import Unealta

UTILIZATOR = uuid4()


class ClientFals:
    """Client de model care intoarce raspunsuri dinainte stabilite."""

    def __init__(self, raspunsuri: list[RaspunsModel]) -> None:
        self.raspunsuri = list(raspunsuri)
        self.cereri: list[list[dict]] = []

    async def completeaza(self, mesaje, unelte=None):
        self.cereri.append(list(mesaje))
        return self.raspunsuri.pop(0)


def test_tool_urile_nu_expun_identitatea_catre_model() -> None:
    unelte = financiar_tools.construieste(AnalizaService(None, None), UTILIZATOR)

    assert {u.nume for u in unelte} == {
        "obtine_sold",
        "obtine_cashflow_lunar",
        "obtine_tranzactii_recente",
        "obtine_neregularitati",
    }
    for unealta in unelte:
        proprietati = unealta.definitie()["function"]["parameters"]["properties"]
        assert "user_id" not in proprietati and "id_user" not in proprietati


def test_fiecare_agent_devine_un_tool_de_delegare() -> None:
    agent = AgentIndisponibil("actiuni", "Executa operatiuni.", "Nu inca.")

    definitie = _unealta_de_delegare(agent, UTILIZATOR, []).definitie()["function"]

    assert definitie["name"] == "deleaga_actiuni"
    assert list(definitie["parameters"]["properties"]) == ["sarcina"]


@pytest.mark.anyio
async def test_delegarea_nu_pretinde_ca_a_executat_ceva() -> None:
    agent = AgentIndisponibil("actiuni", "Executa operatiuni.", "Transferurile se fac din ecran.")
    jurnal: list[ApelAgent] = []

    rezultat = await _unealta_de_delegare(agent, UTILIZATOR, jurnal).executa(
        sarcina="trimite 100 lei"
    )

    assert rezultat["disponibil"] is False
    assert jurnal[0].agent == "actiuni" and jurnal[0].disponibil is False


@pytest.mark.anyio
async def test_agentul_indisponibil_intoarce_rezultat_marcat() -> None:
    rezultat = await AgentIndisponibil("rag", "Intrebari.", "Nu am baza.").executa("x")

    assert isinstance(rezultat, RezultatAgent) and not rezultat.disponibil


@pytest.mark.anyio
async def test_bucla_executa_tool_ul_cerut_si_trimite_rezultatul_inapoi() -> None:
    apelat = {}

    async def obtine_sold() -> dict:
        apelat["da"] = True
        return {"total_disponibil": 1234.5}

    unealta = Unealta(nume="obtine_sold", descriere="Soldul.", executa=obtine_sold)
    client = ClientFals(
        [
            RaspunsModel(text="", apeluri=[CerereTool(id="1", nume="obtine_sold", argumente={})]),
            RaspunsModel(text="Ai 1.234,50 RON."),
        ]
    )

    text, folosite, pasi = await ruleaza_bucla(
        client, "instructiuni", [unealta], [{"role": "user", "content": "cat am?"}],
        max_pasi=5, user_id=UTILIZATOR, nume_agent="test",
    )

    assert apelat == {"da": True}
    assert (text, folosite, pasi) == ("Ai 1.234,50 RON.", ["obtine_sold"], 2)
    # Rezultatul tool-ului trebuie sa ajunga inapoi la model in a doua cerere.
    roluri = [m["role"] for m in client.cereri[1]]
    assert roluri == ["system", "user", "assistant", "tool"]


@pytest.mark.anyio
async def test_un_tool_inventat_nu_darama_requestul() -> None:
    client = ClientFals(
        [
            RaspunsModel(text="", apeluri=[CerereTool(id="1", nume="nu_exista", argumente={})]),
            RaspunsModel(text="Nu pot face asta."),
        ]
    )

    text, _, _ = await ruleaza_bucla(
        client, "i", [], [{"role": "user", "content": "x"}],
        max_pasi=5, user_id=UTILIZATOR, nume_agent="test",
    )

    assert text == "Nu pot face asta."
    assert "eroare" in client.cereri[1][-1]["content"]


@pytest.mark.anyio
async def test_bucla_se_opreste_la_plafon() -> None:
    async def mereu() -> dict:
        return {}

    unealta = Unealta(nume="mereu", descriere="x", executa=mereu)
    client = ClientFals(
        [RaspunsModel(text="", apeluri=[CerereTool(id=str(i), nume="mereu", argumente={})])
         for i in range(10)]
    )

    _, folosite, pasi = await ruleaza_bucla(
        client, "i", [unealta], [{"role": "user", "content": "x"}],
        max_pasi=3, user_id=UTILIZATOR, nume_agent="test",
    )

    assert pasi == 3 and len(folosite) == 3


@pytest.mark.anyio
async def test_apelul_repetat_nu_executa_tool_ul_a_doua_oara() -> None:
    executari = []

    async def obtine_sold() -> dict:
        executari.append(1)
        return {"total_disponibil": 100.0}

    unealta = Unealta(nume="obtine_sold", descriere="Soldul.", executa=obtine_sold)
    client = ClientFals(
        [
            RaspunsModel(
                text="",
                apeluri=[
                    CerereTool(id="1", nume="obtine_sold", argumente={}),
                    CerereTool(id="2", nume="obtine_sold", argumente={}),
                ],
            ),
            RaspunsModel(text="Ai 100 RON."),
        ]
    )

    await ruleaza_bucla(
        client, "i", [unealta], [{"role": "user", "content": "cat am?"}],
        max_pasi=5, user_id=UTILIZATOR, nume_agent="test",
    )

    # Modelul a cerut de doua ori; tool-ul s-a executat o data.
    assert len(executari) == 1

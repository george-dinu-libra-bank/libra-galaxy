"""Bucla de tool-calling de pe traseul „cont blocat".

Modelul e inlocuit cu unul fals: ce se verifica aici e bucla, nu inspiratia lui.
"""

import pytest

from app.agents.base import AgentAnswer
from app.context.builder import AssembledContext
from app.agents.transaction_intelligence import (
    TransactionIntelligenceAgent,
    _e_cont_blocat,
    _sesizare_din_fapte,
)
from app.providers.base import ApelTool, ChatCompletion
from app.tools.base import ToolResult


class _ModelFals:
    """Intoarce, pe rand, raspunsurile pregatite."""

    deployment = "fals"

    def __init__(self, raspunsuri: list[ChatCompletion]) -> None:
        self._raspunsuri = raspunsuri
        self.apeluri_primite: list[list[dict] | None] = []

    async def complete(self, messages, tools=None):
        self.apeluri_primite.append(tools)
        return self._raspunsuri.pop(0) if self._raspunsuri else _text("gata")


def _text(t: str) -> ChatCompletion:
    return ChatCompletion(text=t, tokens_in=0, tokens_out=0, tokens_cached=0, deployment="fals")


def _cere_tool(subiect: str, rezumat: str) -> ChatCompletion:
    return ChatCompletion(
        text="", tokens_in=0, tokens_out=0, tokens_cached=0, deployment="fals",
        apeluri=(ApelTool(id="1", nume="pregateste_sesizare",
                          argumente={"subiect": subiect, "rezumat": rezumat}),),
    )


def _conturi(blocat: bool) -> list[ToolResult]:
    return [
        ToolResult(
            tool_name="get_accounts", success=True,
            data={"accounts": [{"id": "c1", "is_blocked": blocat}]},
        )
    ]


# Context gol: testele de aici verifica bucla, nu ce intra in prompt.
_CONTEXT = AssembledContext(sections=[], truncated_sections=[])


async def _raspunde(model, tool_results) -> AgentAnswer:
    return await TransactionIntelligenceAgent().respond(
        principal=None, user_text="de ce e blocat contul?", context=_CONTEXT,
        tool_results=tool_results, chat_provider=model,
    )


# ---------------------------------------------------------------------------


def test_contul_blocat_e_recunoscut_din_rezultate() -> None:
    assert _e_cont_blocat(_conturi(True)) is True
    assert _e_cont_blocat(_conturi(False)) is False


@pytest.mark.anyio
async def test_uneltele_se_ofera_doar_cand_contul_chiar_e_blocat() -> None:
    """Altfel modelul i-ar pregati o sesizare cuiva care doar intreaba ce inseamna."""
    model = _ModelFals([_text("Contul tau e in regula.")])

    await _raspunde(model, _conturi(False))

    assert model.apeluri_primite == [None]


@pytest.mark.anyio
async def test_sesizarea_ceruta_de_model_ajunge_in_raspuns() -> None:
    model = _ModelFals([
        _cere_tool("Cont blocat", "Contul meu e blocat de ieri si nu inteleg de ce."),
        _text("Am pregatit sesizarea, o trimiti tu."),
    ])

    raspuns = await _raspunde(model, _conturi(True))

    assert raspuns.actiune is not None
    assert raspuns.actiune.tip == "sesizare_suport"
    assert "blocat de ieri" in raspuns.actiune.rezumat
    assert raspuns.text == "Am pregatit sesizarea, o trimiti tu."


@pytest.mark.anyio
async def test_un_rezumat_prea_scurt_al_modelului_e_inlocuit() -> None:
    """Textul prost al modelului se respinge, dar omul tot primeste butonul:
    cade pe varianta compusa din fapte."""
    model = _ModelFals([_cere_tool("Cont", "x"), _text("Nu am putut.")])

    raspuns = await _raspunde(model, _conturi(True))

    assert raspuns.actiune is not None
    assert raspuns.actiune.context.get("compus") == "determinist"


@pytest.mark.anyio
async def test_butonul_apare_si_daca_modelul_nu_cere_tool_ul() -> None:
    """Plasa de siguranta: promptul comun il invata pe model sa fie prudent, iar
    daca refuza sa ceara tool-ul, omul ramanea sa scrie singur ce sistemul stia
    oricum."""
    model = _ModelFals([_text("Suna la 0800 970 501.")])

    raspuns = await _raspunde(model, _conturi(True))

    assert raspuns.actiune is not None
    assert raspuns.actiune.context.get("compus") == "determinist"


@pytest.mark.anyio
async def test_contul_neblocat_nu_primeste_buton() -> None:
    model = _ModelFals([_text("Contul tau e in regula.")])

    raspuns = await _raspunde(model, _conturi(False))

    assert raspuns.actiune is None


def _cu_mesaj(corp: str):
    return [
        ToolResult(
            tool_name="get_bank_messages", success=True,
            data={"messages": [{"kind": "blocare", "body": corp}]},
        )
    ]


def test_sesizarea_compusa_contine_mesajul_bancii_si_intrebarea() -> None:
    """Doar lucruri verificabile: ce a comunicat banca si ce a intrebat omul."""
    actiune = _sesizare_din_fapte("de ce e blocat?", _cu_mesaj("Activitate neobisnuita."))

    assert "Activitate neobisnuita." in actiune.rezumat
    assert "de ce e blocat?" in actiune.rezumat


def test_nota_analistului_nu_se_citeaza_inapoi_bancii() -> None:
    """Nota ajunge la client, dar nimeni nu scrie bancii „Observatia analistului:
    suspect de frauda" in propria lui scrisoare."""
    corp = (
        "Retragerile au fost oprite temporar."
        + chr(10) * 2
        + "Observația analistului: suspect de fraudă"
    )

    actiune = _sesizare_din_fapte("de ce?", _cu_mesaj(corp))

    assert "Retragerile au fost oprite temporar." in actiune.rezumat
    assert "analistului" not in actiune.rezumat
    assert "suspect de frauda" not in actiune.rezumat


def test_sesizarea_e_scrisa_formal_si_cu_diacritice() -> None:
    """E o scrisoare pe care o semneaza clientul, nu o insiruire de fapte."""
    actiune = _sesizare_din_fapte("de ce?", _cu_mesaj("Motiv."))

    assert actiune.rezumat.startswith("Stimată echipă")
    assert actiune.rezumat.rstrip().endswith("mulțumesc.")
    # Diacriticele conteaza: textul e citit de un om, nu e un identificator.
    assert any(c in actiune.rezumat for c in "ăâîșț")


@pytest.mark.anyio
async def test_bucla_nu_ruleaza_la_nesfarsit() -> None:
    """Un model care cere acelasi tool la infinit nu trebuie sa manance tura."""
    model = _ModelFals([_cere_tool("Cont blocat", "Acelasi lucru, iar si iar.") for _ in range(20)])

    await _raspunde(model, _conturi(True))

    # Un apel initial plus cel mult MAX_PASI reveniri.
    assert len(model.apeluri_primite) <= 4

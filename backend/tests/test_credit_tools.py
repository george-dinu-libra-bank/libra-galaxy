"""Creditele, vazute de asistent.

Pana acum niciun agent nu stia nimic despre ele: „de ce mi-a fost respinsa
cererea?" ajungea la RAG si primea brosura produsului, nu dosarul omului.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.security import Principal
from app.tools.base import RiskLevel, SideEffect
from app.tools.credit_tools import build_credit_tools
from app.tools.knowledge_tools import build_knowledge_tools

# `Principal.user_id` e str, nu UUID — repository-ul face `str()` oricum.
ID_USER = "6d1eaaec-0000-4000-8000-000000000001"


class _RepoFals:
    def __init__(self) -> None:
        self.id_cerere = str(uuid4())
        self.id_credit = str(uuid4())

    async def cereri_utilizator(self, user_id):
        assert user_id == ID_USER  # tool-ul nu poate cere dosarul altcuiva
        return [{
            "id": self.id_cerere, "status": "respinsa", "suma_ceruta": "30000",
            "luni": 48, "rata_lunara": None, "creat_la": "2026-08-01T10:00:00Z",
            "oferta_expira_la": None, "scor": 41, "dti": "0.52",
            "explicatie": "Gradul de indatorare depaseste pragul.",
            "motive": [{"cod": "dti_prea_mare", "text": "DTI 52%"}],
            "venit_folosit": "4850", "obligatii_folosite": "1200",
        }]

    async def credite_utilizator(self, user_id):
        return [{
            "id": self.id_credit, "status": "activ", "principal": "20000",
            "sold_ramas": "17500", "rata_lunara": "512.34", "luni": 48,
            "dobanda_anuala": "0.099", "data_acordarii": "2026-06-01",
        }]

    async def rate(self, id_credit):
        return [
            {"numar": 1, "scadenta": "2026-07-01", "total": "512.34", "status": "platita"},
            {"numar": 2, "scadenta": "2026-08-01", "total": "512.34", "status": "scadenta"},
        ]

    async def produs(self, slug):
        return {
            "slug": slug, "nume": "Galaxy Flex Personal", "dobanda_anuala": "0.099",
            "suma_min": "1000", "suma_max": "150000", "luni_min": 6, "luni_max": 120,
        }


def _tool(nume: str):
    unelte = {t.name: t for t in build_credit_tools(_RepoFals())}
    return unelte[nume]


PRINCIPAL = Principal(user_id=ID_USER, role="client", access_token="t")


async def test_niciun_tool_nu_scrie_singur() -> None:
    """Asistentul explica ce s-a hotarat si pregateste; nu hotaraste si nu scrie.

    Singurul care se apropie de o scriere e `prepare_credit_application`, si acela
    doar pregateste: cere confirmare si nu are voie sa fie MUTATES. Depunerea are
    nevoie de acordul omului pentru Biroul de Credit, iar un model care il deduce
    dintr-o conversatie nu e acelasi lucru cu omul care bifeaza casuta.
    """
    for unealta in build_credit_tools(_RepoFals()):
        assert unealta.side_effect is not SideEffect.MUTATES
        if unealta.side_effect is SideEffect.PREPARES_MUTATION:
            assert unealta.requires_confirmation is True
        else:
            assert unealta.side_effect in (SideEffect.READ_ONLY, SideEffect.COMPUTE)
            assert unealta.risk_level is RiskLevel.LOW
            assert unealta.requires_confirmation is False


async def test_decizia_vine_cu_motivele_motorului() -> None:
    unealta = _tool("get_credit_decision")

    date = await unealta.callback(PRINCIPAL, {})

    assert date["found"] is True
    assert date["status"] == "respinsa"
    assert date["scor"] == 41
    assert "indatorare" in date["explicatie"]
    assert date["motive"][0]["cod"] == "dti_prea_mare"
    # Textul spune si ce urmeaza, ca modelul sa nu inventeze el pasul urmator.
    assert "depune alta" in date["ce_urmeaza"]


async def test_un_id_strain_nu_deschide_dosarul_altcuiva() -> None:
    """Filtrarea se face pe lista proprie, nu pe id-ul primit de la model."""
    unealta = _tool("get_credit_decision")

    date = await unealta.callback(PRINCIPAL, {"application_id": str(uuid4())})

    # Cade inapoi pe cererea proprie cea mai recenta, niciodata pe alta.
    assert date["found"] is True
    assert date["status"] == "respinsa"


async def test_urmatoarea_rata_o_sare_pe_cea_platita() -> None:
    date = await _tool("get_next_installment").callback(PRINCIPAL, {})

    assert len(date["installments"]) == 1
    assert date["installments"][0]["numar_rata"] == 2


async def test_simularea_merge_prin_motor_nu_prin_model() -> None:
    """Cifra trebuie sa fie chiar cea pe care ar da-o fluxul real de creditare."""
    from decimal import Decimal

    from app.credit import amortizare

    date = await _tool("simulate_credit").callback(PRINCIPAL, {"suma": "30000", "luni": 48})

    principal = amortizare.bani_din_lei(Decimal("30000"))
    asteptat = amortizare.lei_din_bani(
        amortizare.rata_lunara_bani(principal, Decimal("0.099"), 48)
    )
    assert date["rata_lunara"] == pytest.approx(float(asteptat))
    assert date["cost_total"] > 0


async def test_simularea_refuza_valori_absurde() -> None:
    unealta = _tool("simulate_credit")

    assert "error" in await unealta.callback(PRINCIPAL, {"suma": "-5", "luni": 12})
    assert "error" in await unealta.callback(PRINCIPAL, {"suma": "abc", "luni": 12})


# --- lantul intreg: intentie -> agent -> tool-uri ---------------------------
#
# Separarea dosar/brosura (care intrebare merge la credit_advisor vs. la RAG)
# e acum decisa prin rationament LLM (orchestration/llm_router.py), nu prin
# clasificare determinista de testat pe un string — testele de mai jos verifica
# ce a mai ramas determinist: ce agent detine eticheta si ce tool-uri cere
# odata ce a primit-o. Intre ele era o gaura prin care a trecut un bug intreg: tool-urile
# erau atasate lui `financial_advisor`, care nu foloseste registrul
# (`select_tools()` intoarce mereu []). Erau inregistrate si imposibil de cerut,
# iar asistentul raspundea „nu am acces la deciziile bancii".


def test_intentia_de_credit_ajunge_la_agentul_de_credit() -> None:
    from app.agents.specs import ALL_AGENT_SPECS

    proprietari = [s.agent_id for s in ALL_AGENT_SPECS if "credit_question" in s.intents]
    assert proprietari == ["credit_advisor"]


def test_agentul_de_credit_chiar_cere_tool_urile() -> None:
    """Regresia: un agent care nu cere niciun tool primeste zero date si
    improvizeaza — exact ce se intampla in ecran."""
    from app.agents.credit_advisor import CreditAdvisorAgent

    agent = CreditAdvisorAgent()

    cerute = {t.name for t in agent.select_tools("de ce mi-a fost respinsa cererea?", "credit_question")}
    assert "get_credit_decision" in cerute

    cerute = {t.name for t in agent.select_tools("ce rata am luna asta?", "credit_question")}
    assert "get_next_installment" in cerute

    # Starea dosarelor merge mereu: fara ea n-are despre ce vorbi.
    for intrebare in ("ce credite am?", "cand am rata?", "de ce am fost respins?"):
        cerute = {t.name for t in agent.select_tools(intrebare, "credit_question")}
        assert "get_credit_applications" in cerute


def test_simularea_se_cere_doar_cu_suma_si_durata() -> None:
    from app.agents.credit_advisor import CreditAdvisorAgent

    agent = CreditAdvisorAgent()

    alese = {t.name: t.args for t in agent.select_tools("ce rata as avea la 30.000 pe 4 ani?", "credit_question")}
    # "30000", nu "30000.0": suma ajunge in URL-ul formularului, iar `str(float)`
    # lasa un ".0" pe care tool-ul il taia apoi tacit cu `int()`.
    assert alese["simulate_credit"] == {"suma": "30000", "luni": 48}

    # Fara cifre n-are ce calcula, iar o eroare de tool ar trebui explicata de model.
    fara = {t.name for t in agent.select_tools("as vrea un credit", "credit_question")}
    assert "simulate_credit" not in fara


class _RetrievalFals:
    """Nu se cauta nimic in testul asta — se verifica doar cine are voie sa ceara
    tool-ul, adica exact ce citeste executorul inainte sa-l ruleze."""

    async def search(self, query, profile=None):
        return []


def test_tool_urile_sunt_atasate_agentului_care_le_poate_cere() -> None:
    """Punctul exact unde a fost bug-ul: registrul si spec-ul trebuie sa cada la fel."""
    from app.agents.specs import CREDIT_ADVISOR

    ale_registrului = {
        t.name for t in build_credit_tools(_RepoFals())
        if "credit_advisor" in t.allowed_agents
    }
    # `search_bank_knowledge` vine din alt constructor (knowledge_tools), dar
    # agentul chiar il cere de cand raspunde si la intrebari despre produs — deci
    # se verifica separat ca e permis, nu se scoate din socoteala.
    assert ale_registrului == set(CREDIT_ADVISOR.tool_names) - {"search_bank_knowledge"}

    din_cunostinte = build_knowledge_tools(_RetrievalFals())[0]
    assert din_cunostinte.name == "search_bank_knowledge"
    assert "credit_advisor" in din_cunostinte.allowed_agents, (
        "spec-ul cere tool-ul, dar executorul l-ar filtra tacit"
    )


# --- pregatirea cererii din conversatie ------------------------------------


def test_datele_formularului_se_citesc_din_fraza() -> None:
    """Orchestratorul cheama `select_tools` o singura data pe tura, fara bucla in
    care modelul sa umple argumentele treptat — deci le extragem determinist."""
    from app.agents.credit_advisor import _date_cerere, _normalizeaza_cu_harta

    original = (
        "vreau sa depun o cerere de credit de 30000 lei pe 48 de luni, "
        "lucrez la ACME Software de 3 ani, castig 5200 net si am rate de 800"
    )
    text, harta = _normalizeaza_cu_harta(original)
    date = _date_cerere(text, harta, original)

    assert date["suma"] == "30000"
    assert date["luni"] == 48, "durata creditului, nu vechimea la angajator"
    assert date["venit_declarat"] == "5200"
    assert date["obligatii_declarate"] == "800"
    # Numele se opreste la cuvantul de legatura (altfel ajungea „ACME Software de
    # 3 ani") si pastreaza majusculele din textul original: valoarea asta ajunge
    # in formular, sub ochii unui analist.
    assert date["angajator"] == "ACME Software"
    assert date["vechime_angajator_luni"] == 36


def test_suma_nu_e_furata_de_venit_cand_venitul_e_spus_primul() -> None:
    """`_cifre` lua primul numar >= 1000 din fraza, oricare ar fi fost el.

    Testul vechi folosea doar ordinea convenabila (suma inaintea venitului), deci
    n-a prins niciodata ca „castig 5200 net, vreau un credit de 30000" completa
    formularul cu 5200 ca suma imprumutata.
    """
    from app.agents.credit_advisor import _date_cerere, _normalizeaza_cu_harta

    original = "castig 5200 net, vreau un credit de 30000 lei pe 48 de luni"
    text, harta = _normalizeaza_cu_harta(original)
    date = _date_cerere(text, harta, original)

    assert date["suma"] == "30000"
    assert date["venit_declarat"] == "5200"


def test_vechimea_se_citeste_si_cu_de_intre_numar_si_unitate() -> None:
    """„36 de luni" e la fel de romanesc ca „36 luni".

    Fara "de" optional in regex, tool-ul intorcea vechimea ca `missing` si agentul
    reintreba exact ce tocmai spusese omul.
    """
    from app.agents.credit_advisor import _date_cerere, _normalizeaza_cu_harta

    for fraza in ("am vechime de 36 de luni", "am vechime de 36 luni"):
        original = f"vreau un credit de 30000 pe 48 de luni, lucrez la ACME, {fraza}"
        text, harta = _normalizeaza_cu_harta(original)
        assert _date_cerere(text, harta, original)["vechime_angajator_luni"] == 36, fraza


async def test_fara_date_tool_ul_spune_ce_lipseste() -> None:
    """Asa poate modelul cere exact bucata care lipseste, nu tot chestionarul."""
    date = await (_tool("prepare_credit_application").callback(PRINCIPAL, {}))

    assert date["ready"] is False
    assert "numele angajatorului" in date["missing"]


async def test_cererea_pregatita_nu_e_depusa() -> None:
    """Depunerea cere `consimtamant=true` — un acord dat de om, nu dedus de model."""
    date = await (_tool("prepare_credit_application").callback(PRINCIPAL, {
        "suma": "30000", "luni": 48, "venit_declarat": "5200",
        "angajator": "ACME Software", "vechime_angajator_luni": 36,
        "obligatii_declarate": "800",
    }))

    assert date["ready"] is True
    assert date["rata_lunara"] > 0
    assert date["link"].startswith("/credite/cerere?")
    assert "suma=30000" in date["link"] and "luni=48" in date["link"]
    # Nimic nu s-a scris in baza: tool-ul doar pregateste.
    assert "id" not in date


async def test_suma_in_afara_limitelor_produsului_e_oprita_aici() -> None:
    date = await (_tool("prepare_credit_application").callback(PRINCIPAL, {
        "suma": "5000000", "luni": 48, "venit_declarat": "5200",
        "angajator": "ACME", "vechime_angajator_luni": 36,
        "obligatii_declarate": "0",
    }))

    assert date["ready"] is False
    assert "intre" in date["error"]

"""Promptul de sistem trebuie sa lase agentul sa ceara datele care lipsesc.

De ce exista fisierul asta: `df9499d` a adaugat in `build_system_prompt` o regula
scrisa pentru RAG — „nu adauga sectiuni despre ce nu e documentat, spune ca nu ai
informatii si trimite la un operator". Buna acolo, dar
`prepare_credit_application` functioneaza exact invers: intoarce `missing` TOCMAI
ca modelul sa intrebe ce lipseste. Rezultatul: in loc de „ce venit net ai?", omul
primea „nu am informatii, contacteaza un operator", si formularul de credit nu se
mai completa niciodata.

Regresia n-a fost prinsa de nimic, fiindca `ChatProvider` e mockuit in toate
testele — traia doar in textul promptului, unde nu se uita nicio aserttiune.
Testele de aici sunt acea aserttiune: urmatoarea rescriere a regulii nu mai poate
sterge exceptia in tacere.
"""

from __future__ import annotations

from app.agents.base import build_system_prompt
from app.agents.specs import CREDIT_ADVISOR, DOCUMENT_INTELLIGENCE
from app.context.builder import AssembledContext


def _prompt(spec) -> str:
    return build_system_prompt(spec, AssembledContext(sections=[], truncated_sections=[]))


def test_promptul_cere_datele_lipsa_in_loc_sa_trimita_la_operator() -> None:
    prompt = _prompt(CREDIT_ADVISOR)

    assert "EXCEPTIE" in prompt
    assert "missing" in prompt
    # Fara asta, regula generala castiga si agentul trimite omul la call center
    # in mijlocul completarii propriului lui formular.
    assert "NU trimiti la" in prompt


def test_regula_generala_ramane_intacta() -> None:
    """Exceptia e o exceptie, nu o slabire: raspunsurile din cunostinte tot n-au
    voie sa insire ce „nu e documentat"."""
    prompt = _prompt(DOCUMENT_INTELLIGENCE)

    assert "nu e documentat" in prompt
    assert "operator uman" in prompt


def test_exceptia_ajunge_la_toti_agentii_nu_doar_la_credite() -> None:
    """`build_system_prompt` e comun; daca maine alt tool intoarce `missing`,
    comportamentul trebuie sa fie deja corect, nu adaugat din nou."""
    assert "EXCEPTIE" in _prompt(DOCUMENT_INTELLIGENCE)

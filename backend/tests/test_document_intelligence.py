from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from app.agents.base import AttachmentContext
from app.agents.document_intelligence import DocumentIntelligenceAgent
from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatCompletion, ChatMessage
from app.tools.base import ToolResult

UTILIZATOR_RO = Principal(user_id=str(uuid4()), role="customer", permissions={"assistant:use"}, locale="ro")
UTILIZATOR_EN = Principal(user_id=str(uuid4()), role="customer", permissions={"assistant:use"}, locale="en")
CONTEXT_GOL = AssembledContext(sections=[], truncated_sections=[])


@dataclass
class ChatProviderFals:
    deployment: str = "test-deployment"
    mesaje_primite: list[list[ChatMessage]] = field(default_factory=list)
    text_raspuns: str = "raspuns"

    async def complete(self, messages: list[ChatMessage]) -> ChatCompletion:
        self.mesaje_primite.append(messages)
        return ChatCompletion(text=self.text_raspuns, tokens_in=1, tokens_out=1, tokens_cached=0, deployment=self.deployment)


@pytest.mark.anyio
async def test_no_hits_still_calls_the_model_with_the_off_topic_rule():
    """Raportat live: 'poti sa imi zici un banc despre bani?' (o gluma, nu o
    intrebare bancara) trebuie sa primeasca un refuz clar de scop. Inainte se
    scurtcircuita cu un text fix, fara niciun apel de model — acum modelul e
    apelat intotdeauna, ghidat de regula de refuz off-topic deja prezenta in
    build_system_prompt() (comuna tuturor agentilor), plus grounding_rule-ul
    explicit pentru cazul "nicio potrivire" adaugat aici."""
    agent = DocumentIntelligenceAgent()
    provider = ChatProviderFals()

    await agent.respond(UTILIZATOR_RO, "poti sa imi zici un banc despre bani?", CONTEXT_GOL, [], provider)

    assert len(provider.mesaje_primite) == 1
    system_prompt = provider.mesaje_primite[0][0].content
    assert "domeniul bancar" in system_prompt
    assert "Nu exista fragmente din baza de cunostinte pentru aceasta intrebare" in system_prompt


@pytest.mark.anyio
async def test_no_hits_in_english_still_calls_the_model():
    agent = DocumentIntelligenceAgent()
    provider = ChatProviderFals()

    await agent.respond(UTILIZATOR_EN, "tell me a joke about money", CONTEXT_GOL, [], provider)

    assert len(provider.mesaje_primite) == 1
    system_prompt = provider.mesaje_primite[0][0].content
    assert "banking-related questions" not in system_prompt  # asta era doar in vechiul text fix, sters
    assert "domeniul bancar" in system_prompt  # regula de refuz off-topic ramane, in prompt, indiferent de locale


@pytest.mark.anyio
async def test_system_prompt_warns_against_off_topic_answers_from_loose_hits():
    """Chiar cand EXISTA hit-uri (posibil doar prin suprapunere lexicala, ex.
    cuvantul 'bani'), promptul trebuie sa instruiasca explicit modelul sa nu
    forteze un raspuns dintr-un fragment irelevant."""
    agent = DocumentIntelligenceAgent()
    provider = ChatProviderFals()
    tool_results = [
        ToolResult(
            tool_name="search_bank_knowledge", success=True,
            data={"hits": [{"document_id": "credite/eligibilitate", "section": None, "text": "text", "score": 0.55}]},
        )
    ]

    await agent.respond(UTILIZATOR_RO, "poti sa imi zici un banc despre bani?", CONTEXT_GOL, tool_results, provider)

    system_prompt = provider.mesaje_primite[0][0].content
    assert "domeniul bancar" in system_prompt
    assert "cuvinte" in system_prompt


def test_credit_intent_narrows_search_to_credite_category():
    """credit_intent e eticheta care garanteaza cel mai clar subiectul, chiar
    daca ajunge la document_intelligence (nu la credit_advisor) pentru partea
    informativa — deci e singura unde ingustarea pe categorie (migratia 0033)
    e sigur justificata."""
    selections = DocumentIntelligenceAgent().select_tools("vreau un credit ipotecar", "credit_intent")

    assert len(selections) == 1
    assert selections[0].args["categorie_hint"] == "credite"


def test_generic_intents_do_not_narrow_by_category():
    for intent in ("document_question", "knowledge_question", "unknown"):
        selections = DocumentIntelligenceAgent().select_tools("ce comisioane are transferul SEPA", intent)
        assert "categorie_hint" not in selections[0].args


@pytest.mark.anyio
async def test_attachment_sent_alone_gets_a_proactive_suggestion_not_a_refusal():
    """Raportat live: trimiterea unei poze fara nicio intrebare trebuie sa
    primeasca o descriere + o sugestie a ce se poate face cu ea — nu refuzul
    generic de scop (care se aplica doar cand chiar nu exista nimic de
    analizat, nici hit-uri, nici atasament)."""
    agent = DocumentIntelligenceAgent()
    provider = ChatProviderFals()
    atasament = AttachmentContext(kind="imagine", filename="chitanta.jpg", image_data_uri="data:image/jpeg;base64,AAA=")

    answer = await agent.respond(UTILIZATOR_RO, "", CONTEXT_GOL, [], provider, attachments=[atasament])

    assert answer.text == "raspuns"
    system_prompt = provider.mesaje_primite[0][0].content
    assert "sugereaza" in system_prompt or "sugerezi" in system_prompt or "sugera" in system_prompt
    assert "NU afirma ca ai facut deja legatura" in system_prompt


@pytest.mark.anyio
async def test_attachment_sent_alone_in_english_uses_the_english_rule():
    agent = DocumentIntelligenceAgent()
    provider = ChatProviderFals()
    atasament = AttachmentContext(kind="imagine", filename="receipt.jpg", image_data_uri="data:image/jpeg;base64,AAA=")

    await agent.respond(UTILIZATOR_EN, "", CONTEXT_GOL, [], provider, attachments=[atasament])

    system_prompt = provider.mesaje_primite[0][0].content
    assert "Do NOT claim you have already linked" in system_prompt

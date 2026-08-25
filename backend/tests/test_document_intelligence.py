from app.agents.document_intelligence import DocumentIntelligenceAgent


def test_credit_intent_narrows_search_to_credite_category():
    """credit_intent e singura intentie care ajunge la document_intelligence
    prin fallback-ul router-ului (routing.py::DEFAULT_AGENT_ID) fara sa fie
    o intrebare generica — deci e singura unde ingustarea pe categorie
    (migratia 0027) e sigur justificata."""
    selections = DocumentIntelligenceAgent().select_tools("vreau un credit ipotecar", "credit_intent")

    assert len(selections) == 1
    assert selections[0].args["categorie_hint"] == "credite"


def test_generic_intents_do_not_narrow_by_category():
    for intent in ("document_question", "knowledge_question", "unknown"):
        selections = DocumentIntelligenceAgent().select_tools("ce comisioane are transferul SEPA", intent)
        assert "categorie_hint" not in selections[0].args

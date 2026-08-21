import pytest

from app.orchestration.intent import classify_intent
from app.orchestration.routing import AgentRouter


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("Ce-ar fi daca aș economisi 500 RON pe luna?", "what_if"),
        ("What if I save 500 RON a month?", "what_if"),
        ("Cât am cheltuit luna asta pe mâncare?", "spending_analysis"),
        ("How much did I spend on food?", "spending_analysis"),
        ("Câți bani am primit pe data de 19 august 2026?", "spending_analysis"),
        ("How much did I receive last week?", "spending_analysis"),
        ("Ce tranzacții recente am?", "spending_analysis"),
        ("Arată-mi istoricul tranzacțiilor", "spending_analysis"),
        ("Câți bani am trimis azi și cui?", "spending_analysis"),
        ("Cine mi-a trimis cei mai mulți bani?", "spending_analysis"),
        ("Cui am trimis bani luna asta?", "spending_analysis"),
        ("How much did I send today?", "spending_analysis"),
        ("Who sent me the most money?", "spending_analysis"),
        ("Cât am în cont?", "account_overview"),
        ("What is my balance?", "account_overview"),
        ("Care este IBAN-ul meu?", "account_overview"),
        ("care esdte iban ul meu?", "account_overview"),
        ("What is my account number?", "account_overview"),
        ("Ce comisioane are transferul SEPA?", "document_question"),
        ("What are the fees for a SEPA transfer?", "document_question"),
        ("Vreau sa fac verificare identitate", "kyc_workflow"),
        ("asdkjhasd random text fara sens", "unknown"),
    ],
)
def test_classify_intent(text, expected_intent):
    assert classify_intent(text) == expected_intent


def test_diacritics_do_not_change_classification():
    with_diacritics = classify_intent("Cât am cheltuit pe abonamente luna asta?")
    without_diacritics = classify_intent("Cat am cheltuit pe abonamente luna asta?")
    assert with_diacritics == without_diacritics == "spending_analysis"


def test_broad_transaction_stems_do_not_swallow_financial_advice():
    # "cum sa economisesc bani" nu contine "tranzact"/"trimis"/"primit" — trebuie
    # sa ramana financial_advice, nu sa fie inghitita de radacinile mai largi.
    assert classify_intent("Cum sa economisesc bani?") == "financial_advice"


def test_more_specific_intent_wins_over_broader_one():
    # Textul contine tipare din ambele categorii ("ce-ar fi daca" si "cheltuit pe"),
    # dar what_if e verificat inaintea spending_analysis, deci trebuie sa castige.
    assert classify_intent("Ce-ar fi daca cheltuit pe mancare creste luna asta?") == "what_if"


def test_router_maps_intent_to_declared_agent():
    router = AgentRouter()
    assert router.select("what_if") == "financial_advisor"
    assert router.select("spending_analysis") == "transaction_intelligence"
    assert router.select("document_question") == "document_intelligence"


def test_router_defaults_unknown_to_document_intelligence():
    router = AgentRouter()
    assert router.select("unknown") == "document_intelligence"
    assert router.select("something_never_declared") == "document_intelligence"

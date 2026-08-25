import pytest

from app.orchestration.intent import classify_intent, starts_with_greeting
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
        ("Exporta-mi tranzactiile intr-un fisier", "export_request"),
        ("Vreau sa descarc extrasul de cont", "export_request"),
        ("Genereaza-mi un pdf cu tranzactiile", "export_request"),
        ("Export my transactions please", "export_request"),
        ("Download my transaction history", "export_request"),
        ("I need an account statement", "export_request"),
        ("Cand expira cardul meu?", "card_question"),
        ("Ce carduri am?", "card_question"),
        ("Ce stil are cardul meu?", "card_question"),
        ("When does my card expire?", "card_question"),
        ("Vreau sa fac un transfer", "transfer_intent"),
        ("Vreau sa fac o tranzactie", "transfer_intent"),
        ("Vreau sa fac o plata", "transfer_intent"),
        ("Sa trimit bani cuiva", "transfer_intent"),
        ("Initiez un transfer", "transfer_intent"),
        ("Make a transfer", "transfer_intent"),
        ("I want to send money", "transfer_intent"),
        ("Start a transfer", "transfer_intent"),
        # Raportat live: "poti sa mi transferi bani?" nu era prins de vechea
        # lista de fraze exacte (doar "vreau sa..."/"fac un..."), fiindca era o
        # cerere politicoasa la persoana a doua, nu la intai.
        ("Poti sa mi transferi bani intr un cont?", "transfer_intent"),
        ("Poti sa imi faci un transfer?", "transfer_intent"),
        ("Ai putea sa transferi 100 de lei catre Ana?", "transfer_intent"),
        ("Can you transfer money to my friend?", "transfer_intent"),
        ("As vrea sa fac un credit,, ce conditii trebuie sa indeplinesc", "credit_intent"),
        ("Vreau un credit", "credit_intent"),
        ("Vreau sa aplic pentru un credit", "credit_intent"),
        ("As vrea un imprumut", "credit_intent"),
        ("I want a loan", "credit_intent"),
        ("Apply for a loan", "credit_intent"),
        ("Vreau sa creez un grup pentru a strange bani pentru o excursie", "group_intent"),
        ("Vreau sa fac un grup", "group_intent"),
        ("Creeaza un grup", "group_intent"),
        ("Create a group", "group_intent"),
        ("Start a savings group", "group_intent"),
        ("salut", "greeting"),
        ("Salut!", "greeting"),
        ("Buna ziua", "greeting"),
        ("Buna", "greeting"),
        ("neata", "greeting"),
        ("Hello", "greeting"),
        ("Hi", "greeting"),
    ],
)
def test_classify_intent(text, expected_intent):
    assert classify_intent(text) == expected_intent


def test_export_request_wins_over_spending_analysis_stem():
    # "tranzact" (spending_analysis) apare si aici, dar export_request e
    # verificat inaintea lui — altfel o cerere de export ar cadea gresit pe
    # spending_analysis si ar ajunge la LLM in loc sa se scurtcircuiteze
    # determinist (orchestrator.py::_handle_export_request).
    assert classify_intent("Exporta-mi tranzactiile din ultima luna") == "export_request"


def test_greeting_does_not_swallow_a_real_question_attached_to_it():
    # "buna" e in lista de salut, dar cand mesajul chiar contine o intrebare
    # reala, aceea trebuie sa castige — salutul e doar fallback-ul de dupa
    # tabela principala, verificat in classify_intent.
    assert classify_intent("Buna, cat am cheltuit luna asta?") == "spending_analysis"


def test_greeting_root_does_not_false_positive_on_longer_question():
    # "buna" apare si ca adjectiv ("oferta buna"), nu doar ca salut. Fraza de
    # mai jos nu se potriveste cu nimic din tabela principala (nu contine
    # "vreau"/"aplic"/"imprumut" din credit_intent) — plafonul de lungime
    # (_GREETING_MAX_CHARS) e ce o tine departe de fallback-ul de salut.
    assert classify_intent("Este o oferta buna la credit ipotecar?") == "unknown"


def test_starts_with_greeting_detects_greeting_plus_real_request():
    # "salut, vreau sa fac un transfer" clasifica drept transfer_intent (asa
    # trebuie), dar salutul nu trebuie sa dispara complet — starts_with_greeting
    # e verificarea separata pe care orchestrator.py o foloseste ca sa atenteze
    # un "Salut, {nume}! " inaintea raspunsului real.
    assert starts_with_greeting("salut, vreau sa fac un transfer") is True
    assert classify_intent("salut, vreau sa fac un transfer") == "transfer_intent"


def test_starts_with_greeting_requires_the_message_to_start_with_it():
    # "buna" ca parte dintr-o alta propozitie nu conteaza — doar cand mesajul
    # chiar INCEPE cu un salut.
    assert starts_with_greeting("cred ca am o oferta buna la credit") is False


def test_starts_with_greeting_does_not_false_positive_on_salutare_prefix():
    # "salut" e prefix al lui "salutare" — trebuie sa nu se opreasca la
    # primul potrivit partial cand exista un cuvant mai lung care se potriveste
    # exact.
    assert starts_with_greeting("Salutare, ce mai faci?") is True


def test_transfer_intent_wins_over_spending_analysis_stem():
    # "tranzactie" contine radacina "tranzact" (spending_analysis), dar
    # transfer_intent e verificat inaintea lui — altfel "vreau sa fac o
    # tranzactie" ar cadea gresit pe spending_analysis in loc sa
    # declanseze scurtcircuitul determinist _handle_transfer_request.
    assert classify_intent("Vreau sa fac o tranzactie de 100 RON") == "transfer_intent"


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
    assert router.select("card_question") == "transaction_intelligence"


def test_router_defaults_unknown_to_document_intelligence():
    router = AgentRouter()
    assert router.select("unknown") == "document_intelligence"
    assert router.select("something_never_declared") == "document_intelligence"


def test_router_defaults_credit_intent_to_document_intelligence():
    # credit_intent nu e inregistrat pe niciun AgentSpec (la fel ca
    # export_request/transfer_intent) — dar spre deosebire de acelea, NU se
    # scurtcircuiteaza in orchestrator.py, ci chiar ajunge la agent prin
    # fallback-ul implicit, ca RAG-ul din document_intelligence sa raspunda
    # la partea informativa (conditii de eligibilitate).
    assert AgentRouter().select("credit_intent") == "document_intelligence"

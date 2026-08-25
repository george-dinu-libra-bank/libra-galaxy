"""Clasificare de intentie determinista, RO/EN, insensibila la diacritice (docs/AI_ARCHITECTURE.md #2).

O tabela de fraze e gratuita, instanta, reproductibila si testabila unitar —
un apel de model pentru "e o intrebare despre cheltuieli?" ar costa latenta si
bani, fara sa fie testabil ieftin. Ordinea conteaza: un tipar mai specific
trebuie verificat inaintea unuia mai general (ex. "what if" inainte de
"cheltuieli").
"""

from __future__ import annotations

import unicodedata


def _normalize(text: str) -> str:
    """casefold + NFKD, apoi elimina toate semnele combinatorii — acopera atat
    ș/ț cu virgula dedesubt cat si varianta veche cu sedila (ş/ţ), fara tabel manual."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


# Ordine: cele mai specifice intentii primele.
_INTENT_PHRASES: list[tuple[str, tuple[str, ...]]] = [
    (
        # Trebuie inaintea lui "spending_analysis": radacina "tranzact" de acolo
        # ar prinde gresit "exporta-mi tranzactiile" ca simpla intrebare de
        # cheltuieli, in loc sa declanseze scurtcircuitul determinist din
        # orchestrator.py (_handle_export_request) — vezi orchestrator.py.
        "export_request",
        (
            "exporta", "export ", "descarc", "download",  # "descarc" acopera descarca/descarcare/descarc-mi
            "extras de cont", "genereaza-mi un pdf", "genereaza un pdf",
            "fisier cu tranzact", "pdf cu tranzact", "document cu tranzact",
            "trimite-mi un fisier", "vreau un fisier", "vreau un document",
            "export transactions", "download my transactions", "export my transactions",
            "account statement", "statement of my transactions",
        ),
    ),
    (
        # Trebuie inaintea lui "spending_analysis": radacina "tranzact" de acolo
        # ar prinde gresit "vreau sa fac o tranzactie" ca o intrebare despre
        # istoricul de tranzactii, in loc sa declanseze scurtcircuitul determinist
        # din orchestrator.py (_handle_transfer_request). Frazele exprima intentia
        # de a FACE ceva (timp prezent, "vreau"/"fac"), nu de a afla ce s-a
        # intamplat deja — de-aia nu se suprapun cu "trimis"/"am trimit" de mai jos.
        "transfer_intent",
        (
            "vreau sa fac un transfer", "vreau sa fac o tranzactie", "vreau sa fac o plata",
            "as vrea sa fac un transfer", "fac un transfer nou", "sa trimit bani cuiva",
            "vreau sa trimit bani", "initiez un transfer", "vreau un transfer",
            # Forme cu "poti"/"ai putea" (cerere politicoasa) — verificat live ca
            # "poti sa mi transferi bani" nu era prins de frazele de mai sus.
            "poti sa transferi", "poti sa imi transferi", "poti sa-mi transferi", "sa mi transferi",
            "sa imi transferi", "poti transfera", "poti face un transfer", "poti sa faci un transfer",
            "poti face o tranzactie", "poti sa faci o tranzactie", "ai putea sa transferi",
            "ai putea face un transfer", "imi transferi bani", "transfera-mi bani", "transfera bani",
            "imi faci un transfer", "sa faci un transfer",
            "fa-mi un transfer", "fa un transfer", "un transfer catre", "trimite bani", "trimite-mi bani",
            "make a transfer", "want to make a transfer", "start a transfer",
            "want to send money", "i want to send money", "new transfer",
            "can you transfer", "can you send money", "transfer money to", "send money to",
        ),
    ),
    (
        # Nu se scurtcircuiteaza ca export_request/transfer_intent — spre
        # deosebire de un transfer, o cerere de credit are un aspect informativ
        # real (conditii de eligibilitate), acoperit de RAG-ul din
        # document_intelligence (galaxy-bank-knowledge/credite/). Doar link-ul
        # de start al cererii e determinist, atasat in handle_message() dupa
        # raspunsul normal al agentului, niciodata inventat de model.
        "credit_intent",
        (
            "vreau sa fac un credit", "as vrea sa fac un credit", "vreau un credit", "as vrea un credit",
            "vreau sa aplic pentru un credit", "vreau sa cer un credit", "poti sa imi faci un credit",
            "cum aplic pentru un credit", "cum fac o cerere de credit", "vreau sa fac o cerere de credit",
            "as vrea un imprumut", "vreau un imprumut", "vreau sa fac un imprumut",
            "want a loan", "i want a loan", "apply for a loan", "apply for a credit",
            "make a loan request", "start a loan application", "want to apply for a loan",
        ),
    ),
    (
        # Scurtcircuit determinist (ca transfer_intent) — o cerere de a crea un
        # grup e pur actiune, fara continut informativ de pastrat pentru un
        # agent, deci nici modelul nu are ce sa adauge.
        "group_intent",
        (
            "vreau sa creez un grup", "vreau sa fac un grup", "as vrea sa creez un grup",
            "as vrea sa fac un grup", "creeaza un grup", "creati un grup", "vreau un grup pentru",
            "strange bani pentru", "sa strangem bani", "vreau sa strang bani cu",
            "create a group", "want to create a group", "i want to create a group",
            "start a savings group", "start a group", "save money together",
        ),
    ),
    (
        "what_if",
        ("ce-ar fi daca", "ce ar fi daca", "daca as economisi", "daca as pune", "what if", "if i save", "if i invest"),
    ),
    (
        "kyc_workflow",
        ("verificare identitate", "kyc", "cunoastere client", "document de identitate", "identity verification"),
    ),
    (
        # Numele a ramas "spending_analysis" (asa e legat in agents/specs.py),
        # dar acopera istoricul de tranzactii in general — cheltuieli, incasari
        # SI trimiteri — nu doar "am cheltuit". Radacini scurte ("tranzact",
        # "trimis", "primit"), nu fraze exacte: o lista de fraze intregi rateaza
        # mereu o conjugare noua (verificat de doua ori live — "am primit" nu
        # prindea "am primiti", "am trimis" nu era acoperit deloc). Radacinile
        # sunt verificate sa nu se suprapuna cu nicio alta categorie de mai jos.
        "spending_analysis",
        (
            "cat am cheltuit", "cheltuieli", "cheltuit pe", "abonamente",
            "tranzact",  # tranzactie/tranzactii/tranzactiilor/tranzactionat
            "trimis", "am trimit", "mi-a trimis", "mi-au trimis",
            "primit", "incasari", "incasat", "venituri",
            "cui am", "cine mi-a", "cine mi-au",
            "how much did i spend", "how much did i send", "spending", "subscriptions",
            "how much did i receive", "received money", "sent money",
            "who sent", "who paid", "my transactions",
            "transaction history", "recent transactions",
        ),
    ),
    (
        "card_question",
        ("card", "carduri", "my card", "card expiry", "when does my card expire", "card details"),
    ),
    (
        "account_overview",
        (
            "cat am in cont", "sold", "solduri", "conturile mele", "iban",
            "my balance", "my accounts", "account balance", "account number",
        ),
    ),
    (
        "financial_advice",
        ("sfat financiar", "cum sa economisesc", "recomandare", "financial advice", "how should i save"),
    ),
    (
        # Inaintea lui "document_question": acela prinde "comision"/"termeni", iar
        # "ce dobanda are creditul meu" e despre dosarul omului, nu despre brosura.
        # Radacini scurte, nu fraze intregi — lectia din comentariul de la
        # "spending_analysis": o lista de fraze rateaza mereu o conjugare noua.
        "credit_question",
        (
            # NU radacina "credit" simpla: "e o oferta buna la credit ipotecar?"
            # e o intrebare despre produs, la care raspunde baza de cunostinte,
            # nu dosarul omului. Aici intra doar formularile personale sau
            # actionabile (exista un test care apara distinctia).
            "creditul meu", "creditele mele", "creditul pe care", "credit am",
            "am un credit", "am credite", "vreau un credit", "vreau credit",
            "as vrea un credit", "pot lua un credit", "sa iau un credit",
            "imprumut",  # imprumut/imprumutul/imprumuturi
            # "rata" simplu ar prinde "declarata", "generata", "adevarata" —
            # radacina e prea scurta ca sa stea singura. De aceea perechi.
            "ce rata", "rata mea", "ratele", "rata lunara", "am rata",
            "cat platesc", "cand am rata", "de plata luna asta",
            "scadent",  # scadenta/scadente/scadenta ratei
            "dae", "adeverint", "cerere de credit", "cererea mea",
            # "respins" prinde respins/respinsa/respingere — in aplicatie doar
            # creditarea respinge ceva. "cerere" simplu ar fura si cererile de
            # plata catre comerciant, deci nu e in lista.
            "respins", "aprobat cererea", "aprobata cererea",
            "rambursare anticipata", "grad de indatorare", "indatorare",
            "loan", "loans", "my installment", "installments", "monthly payment",
            "credit application", "why was i rejected", "early repayment",
        ),
    ),
    (
        "document_question",
        ("politica", "procedura", "comision", "comisioane", "termeni", "regulament", "policy", "fee", "terms"),
    ),
]

# Verificate DUPA tabela de mai sus, nu in ea: "buna" e prea scurt/ambiguu ca
# radacina generala (apare si in "e o oferta buna" — nimic de-a face cu un
# salut). Sigur doar cand nimic mai specific nu s-a potrivit deja — vezi
# classify_intent. Fara asta, "salut" cadea pe "unknown" -> document_intelligence
# -> refuzul generic de RAG ("nu pot raspunde"), gresit pentru un salut simplu.
_GREETING_PHRASES: tuple[str, ...] = (
    "salut", "salutare", "buna ziua", "buna dimineata", "buna seara", "neata",
    "buna", "hello", "hi", "hey", "hola",
)

# Un salut e scurt. Plafonul asta e ce impiedica "buna" (adjectiv) sa
# deturneze o intrebare reala si mai lunga care n-a prins nimic altceva din
# tabela — ex. "Este o oferta buna la credit ipotecar?" ramane "unknown",
# nu "greeting", pentru ca depaseste plafonul.
_GREETING_MAX_CHARS = 30


def starts_with_greeting(text: str) -> bool:
    """True daca mesajul INCEPE cu un salut, indiferent ce urmeaza dupa (ex.
    "salut, vreau sa fac un transfer") — spre deosebire de classify_intent,
    care intoarce un singur intent per mesaj, asta se foloseste separat, ca sa
    se poata atasa un salut personalizat inaintea oricarui alt raspuns
    (vezi orchestrator.py::_greeting_prefix). Fara plafon de lungime: aici nu
    e vorba de a alege intentia principala a mesajului (unde "buna" ar putea
    deturna o intrebare lunga fara alta potrivire), ci doar de un prefix
    aditiv peste orice raspuns real."""
    normalized = _normalize(text).strip()
    for phrase in _GREETING_PHRASES:
        if normalized == phrase:
            return True
        if normalized.startswith(phrase) and not normalized[len(phrase)].isalnum():
            return True
    return False


def classify_intent(text: str) -> str:
    normalized = _normalize(text)

    for intent, phrases in _INTENT_PHRASES:
        if any(phrase in normalized for phrase in phrases):
            return intent

    if len(normalized.strip()) <= _GREETING_MAX_CHARS and any(
        phrase in normalized for phrase in _GREETING_PHRASES
    ):
        return "greeting"

    return "unknown"

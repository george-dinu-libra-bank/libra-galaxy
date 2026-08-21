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
        "document_question",
        ("politica", "procedura", "comision", "comisioane", "termeni", "regulament", "policy", "fee", "terms"),
    ),
]


def classify_intent(text: str) -> str:
    normalized = _normalize(text)

    for intent, phrases in _INTENT_PHRASES:
        if any(phrase in normalized for phrase in phrases):
            return intent

    return "unknown"

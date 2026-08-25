"""Mascare de date sensibile. IBAN-ul propriu NU mai e mascat (GUARDRAILS.md
#12) — e echivalentul unui numar de rutare, nu un secret ca CVV-ul de mai jos,
si e deja aratat complet in restul aplicatiei. Ce ramane aici e strict pentru
date care raman secrete indiferent de context."""

from __future__ import annotations


def mask_card_number(digits: str) -> str:
    """Plasa de siguranta pentru output_guardrail.py — niciun tool nu intoarce
    azi un numar de card (GUARDRAILS.md #13), dar daca un model ar mentiona
    oricum o secventa in acel format, iese mascata la fel ca un IBAN."""
    only_digits = "".join(char for char in digits if char.isdigit())
    if len(only_digits) <= 4:
        return "•" * len(only_digits)
    return f"{'•' * (len(only_digits) - 4)}{only_digits[-4:]}"

"""Redactare determinista a raspunsului final — plasa de siguranta daca
modelul nu respecta instructiunile din prompt (GUARDRAILS.md #14, #23).

Ruleaza pe orice AgentAnswer.text, indiferent de agent — inclusiv pe bucla
delegata din agents/financiar.py, care nu foloseste build_system_prompt()
si deci nu primeste instructiunea "nu mentiona tool-urile" din agents/base.py.
De-asta filtrul sta la nivel de orchestrator, nu in fiecare agent in parte.
"""

from __future__ import annotations

import re

from app.core.redaction import mask_card_number

# IBAN-ul propriu al utilizatorului nu se mai maschează (decizie explicita,
# GUARDRAILS.md #12): e echivalentul unui numar de rutare, aratat deja complet
# in restul aplicatiei (ex. detalii-cont-drawer.tsx) — spre deosebire de
# CVV/PIN/parola de mai jos, care raman secrete si mascate mereu.
_SECRET_LABEL_RE = re.compile(r"(?i)\b(cvv|cvc|pin|parola|password|api[_ -]?key|token)\b\s*[:=]?\s*\S+")
# Niciun tool nu intoarce azi un numar de card (GUARDRAILS.md #13) — plasa
# suplimentara pentru cazul in care modelul ar inventa/mentiona oricum o
# secventa in acel format: fie 13-19 cifre lipite, fie grupate in 4 (formatul
# obisnuit de card). Nu un tipar mai larg gen "cifra + separator repetat": ar
# prinde si liste numerotate obisnuite din text ("1, 2, 3, ... 14").
_CARD_NUMBER_RE = re.compile(r"\b\d{13,19}\b|\b\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{1,4}\b")


def redact(text: str) -> str:
    text = _CARD_NUMBER_RE.sub(lambda match: mask_card_number(match.group(0)), text)
    text = _SECRET_LABEL_RE.sub(lambda match: f"{match.group(1)}: [ascuns]", text)
    return text

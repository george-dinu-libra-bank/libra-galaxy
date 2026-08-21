"""Redactare determinista a raspunsului final — plasa de siguranta daca
modelul nu respecta instructiunile din prompt (GUARDRAILS.md #14, #23).

Ruleaza pe orice AgentAnswer.text, indiferent de agent — inclusiv pe bucla
delegata din agents/financiar.py, care nu foloseste build_system_prompt()
si deci nu primeste instructiunea "nu mentiona tool-urile" din agents/base.py.
De-asta filtrul sta la nivel de orchestrator, nu in fiecare agent in parte.
"""

from __future__ import annotations

import re

from app.core.redaction import mask_iban

_IBAN_RE = re.compile(r"\b([A-Za-z]{2}\d{2}[A-Za-z0-9]{10,30})\b")
_SECRET_LABEL_RE = re.compile(r"(?i)\b(cvv|cvc|pin|parola|password|api[_ -]?key|token)\b\s*[:=]?\s*\S+")


def redact(text: str) -> str:
    text = _IBAN_RE.sub(lambda match: mask_iban(match.group(1)), text)
    text = _SECRET_LABEL_RE.sub(lambda match: f"{match.group(1)}: [ascuns]", text)
    return text

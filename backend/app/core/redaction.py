"""Mascare de date sensibile — o singura implementare, folosita si la sursa
(tools/banking_tools.py, inainte ca IBAN-ul sa ajunga la LLM) si ca plasa de
siguranta (orchestration/output_guardrail.py, pe raspunsul final al oricarui
agent). GUARDRAILS.md #12."""

from __future__ import annotations


def mask_iban(iban: str) -> str:
    if len(iban) <= 8:
        return "•" * len(iban)
    return f"{iban[:4]}{'•' * (len(iban) - 8)}{iban[-4:]}"

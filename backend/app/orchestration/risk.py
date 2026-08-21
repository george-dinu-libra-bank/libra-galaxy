"""Risc derivat din intentie, niciodata din formularea mesajului (docs/AI_ARCHITECTURE.md #2)."""

from __future__ import annotations

from app.tools.base import RiskLevel

_INTENT_RISK: dict[str, RiskLevel] = {
    "kyc_workflow": RiskLevel.MEDIUM,
    # Explicit, desi ar fi oricum implicitul: export-ul e citire proprie,
    # determinista (services/transaction_export_service.py), fara mutatie.
    "export_request": RiskLevel.LOW,
}


def classify_risk(intent: str) -> RiskLevel:
    return _INTENT_RISK.get(intent, RiskLevel.LOW)

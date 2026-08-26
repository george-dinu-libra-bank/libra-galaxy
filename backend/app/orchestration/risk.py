"""Risc derivat din intentie, niciodata din formularea mesajului (docs/AI_ARCHITECTURE.md #2)."""

from __future__ import annotations

from app.tools.base import RiskLevel

_INTENT_RISK: dict[str, RiskLevel] = {
    "kyc_workflow": RiskLevel.MEDIUM,
    # Explicit, desi ar fi oricum implicitul: export-ul e citire proprie,
    # determinista (services/transaction_export_service.py), fara mutatie.
    "export_request": RiskLevel.LOW,
    # Citire proprie (stil/expirare card, fara date sensibile).
    "card_question": RiskLevel.LOW,
    # Doar navigatie spre /transfer — nicio mutatie reala (orchestrator.py::_handle_transfer_request).
    "transfer_intent": RiskLevel.LOW,
    # Raspunsul e informativ (RAG), doar link-ul de start al cererii e determinist.
    "credit_intent": RiskLevel.LOW,
    # Doar navigatie spre /grupuri — nicio mutatie reala (orchestrator.py::_handle_group_request).
    "group_intent": RiskLevel.LOW,
    # Raspuns fix, fara date sensibile in afara de numele deja cunoscut al utilizatorului.
    "greeting": RiskLevel.LOW,
    # Doar citire (find_transaction_for_receipt) — scrierea categoriei se face
    # separat, prin ruta determinista apelata de butonul de confirmare, niciodata de aici.
    "categorize_receipt_intent": RiskLevel.LOW,
}


def classify_risk(intent: str) -> RiskLevel:
    return _INTENT_RISK.get(intent, RiskLevel.LOW)

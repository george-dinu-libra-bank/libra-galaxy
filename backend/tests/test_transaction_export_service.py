from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from app.core.security import Principal
from app.rapoarte import pdf_export_tranzactii
from app.repositories.banking_read_repository import TransactionRow
from app.services.transaction_export_service import TransactionExportService

UTILIZATOR = Principal(user_id=str(uuid4()), role="customer", permissions={"assistant:use"})

_TRANZACTII = [
    TransactionRow(
        id="1", amount=120.5, currency="RON", description="Cumparaturi",
        created_at="2026-08-01T10:00:00Z", incoming=False, counterparty_name="Alimentara SRL",
    ),
    TransactionRow(
        id="2", amount=3000.0, currency="RON", description="Salariu",
        created_at="2026-08-05T09:00:00Z", incoming=True, counterparty_name="Angajator SRL",
    ),
]


@dataclass
class BankingFalse:
    tranzactii: list[TransactionRow]

    def list_recent_transactions(self, user_id: str, limit: int = 50) -> list[TransactionRow]:
        return self.tranzactii


@dataclass
class ExportStorageFals:
    urcate: list[tuple[str, bytes, str]] = field(default_factory=list)

    async def upload(self, path: str, content: bytes, content_type: str) -> None:
        self.urcate.append((path, content, content_type))

    async def create_signed_url(self, path: str, seconds: int = 900) -> str:
        return f"https://exemplu.test/{path}"


@pytest.mark.anyio
async def test_generate_transactions_pdf_uploads_valid_pdf_bytes() -> None:
    storage = ExportStorageFals()
    service = TransactionExportService(BankingFalse(_TRANZACTII), storage)

    export = await service.generate_transactions_pdf(UTILIZATOR)

    assert export.url == f"https://exemplu.test/{export.storage_path}"
    assert export.storage_path.startswith(f"{UTILIZATOR.user_id}/")
    assert export.size_bytes > 0
    assert len(storage.urcate) == 1
    path, content, content_type = storage.urcate[0]
    assert path == export.storage_path
    assert content_type == "application/pdf"
    assert content.startswith(b"%PDF")


@pytest.mark.anyio
async def test_generate_transactions_pdf_handles_empty_transaction_list() -> None:
    storage = ExportStorageFals()
    service = TransactionExportService(BankingFalse([]), storage)

    export = await service.generate_transactions_pdf(UTILIZATOR)

    assert export.size_bytes > 0
    _, content, _ = storage.urcate[0]
    assert content.startswith(b"%PDF")


def test_randeaza_produces_valid_pdf_with_transactions():
    from datetime import datetime, timezone

    pdf_bytes = pdf_export_tranzactii.randeaza("user-de-test", _TRANZACTII, datetime.now(timezone.utc))

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 0

"""Export determinist al tranzactiilor proprii, ca PDF (docs/AI_ARCHITECTURE.md).

Declansat de orchestration/orchestrator.py::_handle_export_request, inaintea
oricarui apel de model — datele si formatul vin exclusiv de aici, niciodata
din text generat de LLM (CLAUDE.md #9, #25)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from anyio import to_thread

from app.core.security import Principal
from app.infrastructure.export_storage import ExportStorage
from app.rapoarte import pdf_export_tranzactii
from app.repositories.banking_read_repository import BankingReadRepository

_TRANSACTION_LIMIT = 200


@dataclass(frozen=True)
class GeneratedExport:
    url: str
    filename: str
    storage_path: str
    size_bytes: int


class TransactionExportService:
    def __init__(
        self, banking: BankingReadRepository, storage: ExportStorage, signed_url_seconds: int = 900
    ) -> None:
        self._banking = banking
        self._storage = storage
        self._signed_url_seconds = signed_url_seconds

    async def generate_transactions_pdf(self, principal: Principal) -> GeneratedExport:
        transactions = await to_thread.run_sync(
            lambda: self._banking.list_recent_transactions(principal.user_id, limit=_TRANSACTION_LIMIT)
        )

        generated_at = datetime.now(timezone.utc)
        pdf_bytes = pdf_export_tranzactii.randeaza(principal.user_id, transactions, generated_at)
        filename = pdf_export_tranzactii.nume_fisier(principal.user_id, generated_at)
        storage_path = f"{principal.user_id}/{uuid4().hex}-{filename}"

        await self._storage.upload(storage_path, pdf_bytes, "application/pdf")
        url = await self._storage.create_signed_url(storage_path, self._signed_url_seconds)

        return GeneratedExport(url=url, filename=filename, storage_path=storage_path, size_bytes=len(pdf_bytes))

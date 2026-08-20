"""Fluxul de upload: valideaza, urca in Storage, extrage text (doar PDF), salveaza metadata.

Pozele nu au text extras aici — se trimit ca atare modelului de chat la
momentul raspunsului (agents/base.py:build_user_message).
"""

from __future__ import annotations

import uuid

from app.attachments.extraction import extract_pdf_text
from app.core.errors import ValidationError
from app.infrastructure.attachment_storage import AttachmentStorage
from app.repositories.attachment_repository import Attachment, AttachmentRepository

_ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "image/png": "imagine",
    "image/jpeg": "imagine",
    "image/webp": "imagine",
}


class AttachmentService:
    def __init__(self, storage: AttachmentStorage, repository: AttachmentRepository, max_bytes: int) -> None:
        self._storage = storage
        self._repository = repository
        self._max_bytes = max_bytes

    async def upload(self, user_id: str, filename: str, content_type: str, content: bytes) -> Attachment:
        kind = _ALLOWED_CONTENT_TYPES.get(content_type)
        if kind is None:
            raise ValidationError("Tip de fisier neacceptat. Sunt permise doar PDF, PNG, JPEG si WEBP.")

        if len(content) > self._max_bytes:
            raise ValidationError(f"Fisierul depaseste limita de {self._max_bytes // (1024 * 1024)} MB.")

        storage_path = f"{user_id}/{uuid.uuid4().hex}-{_safe_filename(filename)}"
        await self._storage.upload(storage_path, content, content_type)

        extracted_text = extract_pdf_text(content) if kind == "pdf" else None

        return await self._repository.create(
            user_id=user_id, kind=kind, filename=filename, storage_path=storage_path,
            content_type=content_type, size_bytes=len(content), extracted_text=extracted_text,
        )


def _safe_filename(filename: str) -> str:
    return "".join(char for char in filename if char.isalnum() or char in "._-") or "fisier"

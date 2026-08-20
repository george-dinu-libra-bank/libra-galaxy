"""Upload/download in bucket-ul privat Supabase Storage — singurul loc care vorbeste cu Storage."""

from __future__ import annotations

from supabase import Client

from app.core.errors import PersistenceError


class AttachmentStorage:
    def __init__(self, client: Client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def upload(self, path: str, content: bytes, content_type: str) -> None:
        try:
            self._client.storage.from_(self._bucket).upload(
                path, content, {"content-type": content_type, "upsert": "false"}
            )
        except Exception as exc:
            raise PersistenceError("Nu am putut incarca fisierul.") from exc

    def download(self, path: str) -> bytes:
        try:
            return self._client.storage.from_(self._bucket).download(path)
        except Exception as exc:
            raise PersistenceError("Nu am putut citi fisierul incarcat.") from exc

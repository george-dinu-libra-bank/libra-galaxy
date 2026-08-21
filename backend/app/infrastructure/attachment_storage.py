"""Upload/download in bucket-ul privat Supabase Storage — singurul loc care vorbeste cu Storage."""

from __future__ import annotations

from anyio import to_thread
from supabase import Client

from app.core.errors import PersistenceError


class AttachmentStorage:
    """Fiecare metoda ruleaza apelul sincron supabase-py pe un thread separat
    (to_thread.run_sync), ca sa nu blocheze bucla de evenimente asyncio."""

    def __init__(self, client: Client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def upload(self, path: str, content: bytes, content_type: str) -> None:
        def interogare():
            self._client.storage.from_(self._bucket).upload(
                path, content, {"content-type": content_type, "upsert": "false"}
            )

        try:
            await to_thread.run_sync(interogare)
        except Exception as exc:
            raise PersistenceError("Nu am putut incarca fisierul.") from exc

    async def download(self, path: str) -> bytes:
        def interogare():
            return self._client.storage.from_(self._bucket).download(path)

        try:
            return await to_thread.run_sync(interogare)
        except Exception as exc:
            raise PersistenceError("Nu am putut citi fisierul incarcat.") from exc

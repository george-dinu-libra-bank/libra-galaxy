"""Upload/URL semnat pentru fisiere generate de aplicatie (nu incarcate de utilizator).

Bucket separat de attachment_storage.py: acela e pentru input utilizator, cu
whitelist de content-type gandit pentru asta. Aici uploadul e mereu PDF,
generat determinist de un serviciu (services/transaction_export_service.py),
niciodata de model."""

from __future__ import annotations

from anyio import to_thread
from supabase import Client

from app.core.errors import PersistenceError


class ExportStorage:
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
            raise PersistenceError("Nu am putut incarca fisierul generat.") from exc

    async def create_signed_url(self, path: str, seconds: int = 900) -> str:
        def interogare():
            return self._client.storage.from_(self._bucket).create_signed_url(path, seconds)

        try:
            raspuns = await to_thread.run_sync(interogare)
        except Exception as exc:
            raise PersistenceError("Nu am putut genera linkul de descarcare.") from exc

        url = None
        if isinstance(raspuns, dict):
            url = raspuns.get("signedURL") or raspuns.get("signedUrl")
        if not url:
            raise PersistenceError("Nu am putut genera linkul de descarcare.")
        return url

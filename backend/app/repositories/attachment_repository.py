from __future__ import annotations

from dataclasses import dataclass

from anyio import to_thread
from supabase import Client

from app.core.errors import PersistenceError, ResourceNotFoundError


@dataclass(frozen=True)
class Attachment:
    id: str
    user_id: str
    kind: str
    filename: str
    storage_path: str
    content_type: str
    size_bytes: int
    extracted_text: str | None


class AttachmentRepository:
    """Metadata pentru fisierele din bucket-ul privat 'asistent-atasamente'. Uploadul in Storage
    se face separat, cu clientul de service (infrastructure/supabase_client.py).

    Fiecare metoda ruleaza apelul sincron supabase-py pe un thread separat
    (to_thread.run_sync), ca sa nu blocheze bucla de evenimente asyncio."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def create(
        self, *, user_id: str, kind: str, filename: str, storage_path: str, content_type: str,
        size_bytes: int, extracted_text: str | None,
    ) -> Attachment:
        def interogare():
            return (
                self._client.table("ai_message_attachments")
                .insert(
                    {
                        "id_user": user_id,
                        "tip": kind,
                        "nume_fisier": filename,
                        "storage_path": storage_path,
                        "content_type": content_type,
                        "marime_octeti": size_bytes,
                        "text_extras": extracted_text,
                    }
                )
                .execute()
            )

        result = await to_thread.run_sync(interogare)
        if not result.data:
            raise PersistenceError("Nu am putut salva atasamentul.")
        return self._to_attachment(result.data[0])

    async def get_owned_many(self, user_id: str, attachment_ids: list[str]) -> list[Attachment]:
        if not attachment_ids:
            return []

        def interogare():
            return (
                self._client.table("ai_message_attachments")
                .select("*")
                .eq("id_user", user_id)
                .in_("id", attachment_ids)
                .execute()
            )

        result = await to_thread.run_sync(interogare)
        rows = result.data or []
        if len(rows) != len(set(attachment_ids)):
            raise ResourceNotFoundError("Unul dintre atasamente nu a fost gasit.")
        return [self._to_attachment(row) for row in rows]

    async def attach_to_message(self, attachment_ids: list[str], message_id: str) -> None:
        if not attachment_ids:
            return

        def interogare():
            return self._client.table("ai_message_attachments").update({"id_message": message_id}).in_(
                "id", attachment_ids
            ).execute()

        await to_thread.run_sync(interogare)

    @staticmethod
    def _to_attachment(row: dict) -> Attachment:
        return Attachment(
            id=row["id"], user_id=row["id_user"], kind=row["tip"], filename=row["nume_fisier"],
            storage_path=row["storage_path"], content_type=row["content_type"], size_bytes=row["marime_octeti"],
            extracted_text=row.get("text_extras"),
        )

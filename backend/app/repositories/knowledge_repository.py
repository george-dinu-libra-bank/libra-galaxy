from __future__ import annotations

import logging
from dataclasses import dataclass

from anyio import to_thread
from postgrest.exceptions import APIError
from supabase import Client

from app.core.errors import RetrievalError

logger = logging.getLogger("libra.rag")

# PGRST202 = "function not found in schema cache" — semnul ca migratia
# 0033_rag_categorie_si_cautare_hibrida.sql (care extinde match_knowledge_chunks
# cu p_query_text/p_categories) inca n-a fost rulata pe acest proiect Supabase.
# Migratiile se aplica manual (nu exista acces direct la Postgres din backend),
# deci poate exista un interval intre "codul e pe main" si "migratia a rulat" —
# cautarea nu trebuie sa cada complet in acest interval, doar sa piarda
# temporar filtrul de categorie si plasa de siguranta full-text.
_FUNCTION_NOT_FOUND = "PGRST202"


@dataclass(frozen=True)
class KnowledgeChunkHit:
    chunk_id: str
    document_id: str
    version: int
    section: str | None
    text: str
    metadata: dict
    score: float


class KnowledgeRepository:
    """Singurul strat care citeste/scrie knowledge_documents/knowledge_chunks.

    Fiecare metoda ruleaza apelul sincron supabase-py pe un thread separat
    (to_thread.run_sync), ca sa nu blocheze bucla de evenimente asyncio."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def get_document_checksum(self, document_id: str) -> str | None:
        def interogare():
            return (
                self._client.table("knowledge_documents")
                .select("checksum")
                .eq("document_id", document_id)
                .order("versiune", desc=True)
                .limit(1)
                .maybe_single()
                .execute()
            )

        result = await to_thread.run_sync(interogare)
        # .maybe_single() intoarce None direct cand nu exista niciun rand.
        return result.data["checksum"] if result and result.data else None

    async def upsert_document(
        self, document_id: str, version: int, source: str, document_type: str, language: str,
        checksum: str, audience: str
    ) -> None:
        def interogare():
            return self._client.table("knowledge_documents").upsert(
                {
                    "document_id": document_id,
                    "versiune": version,
                    "sursa": source,
                    "tip_document": document_type,
                    "limba": language,
                    "checksum": checksum,
                    "audienta": audience,
                },
                on_conflict="document_id,versiune",
            ).execute()

        await to_thread.run_sync(interogare)

    async def existing_chunk_ids(self, embedding_key: str) -> set[str]:
        def interogare():
            return (
                self._client.table("knowledge_chunks")
                .select("chunk_id")
                .eq("embedding_key", embedding_key)
                .execute()
            )

        result = await to_thread.run_sync(interogare)
        return {row["chunk_id"] for row in (result.data or [])}

    async def upsert_chunks(self, embedding_key: str, chunks: list[dict]) -> None:
        if not chunks:
            return
        rows = [{**chunk, "embedding_key": embedding_key} for chunk in chunks]

        def interogare():
            return self._client.table("knowledge_chunks").upsert(rows, on_conflict="embedding_key,chunk_id").execute()

        await to_thread.run_sync(interogare)

    async def delete_chunks(self, embedding_key: str, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return

        def interogare():
            return self._client.table("knowledge_chunks").delete().eq("embedding_key", embedding_key).in_(
                "chunk_id", chunk_ids
            ).execute()

        await to_thread.run_sync(interogare)

    async def search(
        self,
        embedding_key: str,
        query_embedding: list[float],
        languages: list[str] | None,
        document_types: list[str] | None,
        audience: str,
        top_k: int,
        min_score: float,
        query_text: str | None = None,
        categories: list[str] | None = None,
    ) -> list[KnowledgeChunkHit]:
        payload = {
            "p_embedding_key": embedding_key,
            "p_query_embedding": query_embedding,
            "p_languages": languages,
            "p_document_types": document_types,
            "p_audience": audience,
            "p_match_count": top_k,
            "p_min_score": min_score,
            "p_query_text": query_text,
            "p_categories": categories,
        }
        legacy_payload = {
            key: value for key, value in payload.items() if key not in ("p_query_text", "p_categories")
        }

        def interogare(body: dict):
            return self._client.rpc("match_knowledge_chunks", body).execute()

        try:
            result = await to_thread.run_sync(interogare, payload)
        except APIError as exc:
            if exc.code != _FUNCTION_NOT_FOUND:
                raise RetrievalError("Cautarea in baza de cunostinte a esuat.") from exc
            logger.warning(
                "match_knowledge_chunks fara p_query_text/p_categories — migratia "
                "0033_rag_categorie_si_cautare_hibrida.sql inca nu a fost aplicata; "
                "cautarea continua fara filtru de categorie si fara plasa de siguranta full-text."
            )
            try:
                result = await to_thread.run_sync(interogare, legacy_payload)
            except Exception as exc_legacy:
                raise RetrievalError("Cautarea in baza de cunostinte a esuat.") from exc_legacy
        except Exception as exc:  # supabase-py surfaces network/RPC errors as generic exceptions
            raise RetrievalError("Cautarea in baza de cunostinte a esuat.") from exc

        rows = result.data or []
        return [
            KnowledgeChunkHit(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                version=row["versiune"],
                section=row.get("sectiune"),
                text=row["continut"],
                metadata=row.get("metadata") or {},
                score=row["scor"],
            )
            for row in rows
        ]

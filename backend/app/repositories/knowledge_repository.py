from __future__ import annotations

from dataclasses import dataclass

from supabase import Client

from app.core.errors import RetrievalError


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
    """Singurul strat care citeste/scrie knowledge_documents/knowledge_chunks."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def get_document_checksum(self, document_id: str) -> str | None:
        result = (
            self._client.table("knowledge_documents")
            .select("checksum")
            .eq("document_id", document_id)
            .order("versiune", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        # .maybe_single() intoarce None direct cand nu exista niciun rand.
        return result.data["checksum"] if result and result.data else None

    def upsert_document(
        self, document_id: str, version: int, source: str, document_type: str, language: str,
        checksum: str, audience: str
    ) -> None:
        self._client.table("knowledge_documents").upsert(
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

    def existing_chunk_ids(self, embedding_key: str) -> set[str]:
        result = (
            self._client.table("knowledge_chunks")
            .select("chunk_id")
            .eq("embedding_key", embedding_key)
            .execute()
        )
        return {row["chunk_id"] for row in (result.data or [])}

    def upsert_chunks(self, embedding_key: str, chunks: list[dict]) -> None:
        if not chunks:
            return
        rows = [{**chunk, "embedding_key": embedding_key} for chunk in chunks]
        self._client.table("knowledge_chunks").upsert(rows, on_conflict="embedding_key,chunk_id").execute()

    def delete_chunks(self, embedding_key: str, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        self._client.table("knowledge_chunks").delete().eq("embedding_key", embedding_key).in_(
            "chunk_id", chunk_ids
        ).execute()

    def search(
        self,
        embedding_key: str,
        query_embedding: list[float],
        languages: list[str] | None,
        document_types: list[str] | None,
        audience: str,
        top_k: int,
        min_score: float,
    ) -> list[KnowledgeChunkHit]:
        try:
            result = self._client.rpc(
                "match_knowledge_chunks",
                {
                    "p_embedding_key": embedding_key,
                    "p_query_embedding": query_embedding,
                    "p_languages": languages,
                    "p_document_types": document_types,
                    "p_audience": audience,
                    "p_match_count": top_k,
                    "p_min_score": min_score,
                },
            ).execute()
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

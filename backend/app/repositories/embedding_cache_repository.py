from __future__ import annotations

from supabase import Client


class EmbeddingCacheRepository:
    """Cache de embeddinguri, chei hash-uite — o intrebare de client nu se stocheaza in clar."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def get_chunk_embedding(self, cache_key: str) -> list[float] | None:
        result = (
            self._client.table("embedding_cache")
            .select("embedding")
            .eq("cache_key", cache_key)
            .maybe_single()
            .execute()
        )
        # .maybe_single() intoarce None direct (nu un raspuns cu .data=None)
        # cand nu exista niciun rand — verificat live cu acest postgrest-py.
        return result.data["embedding"] if result and result.data else None

    def put_chunk_embedding(self, cache_key: str, embedding: list[float]) -> None:
        self._client.table("embedding_cache").upsert(
            {"cache_key": cache_key, "embedding": embedding}, on_conflict="cache_key"
        ).execute()

    def get_query_embedding(self, query_hash: str) -> list[float] | None:
        result = (
            self._client.table("query_embedding_cache")
            .select("embedding")
            .eq("query_hash", query_hash)
            .maybe_single()
            .execute()
        )
        # .maybe_single() intoarce None direct (nu un raspuns cu .data=None)
        # cand nu exista niciun rand — verificat live cu acest postgrest-py.
        return result.data["embedding"] if result and result.data else None

    def put_query_embedding(self, query_hash: str, embedding_key: str, embedding: list[float]) -> None:
        self._client.table("query_embedding_cache").upsert(
            {"query_hash": query_hash, "embedding_key": embedding_key, "embedding": embedding},
            on_conflict="query_hash",
        ).execute()

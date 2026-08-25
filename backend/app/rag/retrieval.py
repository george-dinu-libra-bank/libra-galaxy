"""Regasire cu filtre aplicate inainte de similaritate (docs/AI_ARCHITECTURE.md #7)."""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.base import EmbeddingProvider
from app.rag.indexing import query_cache_key
from app.repositories.embedding_cache_repository import EmbeddingCacheRepository
from app.repositories.knowledge_repository import KnowledgeChunkHit, KnowledgeRepository


@dataclass(frozen=True)
class RetrievalProfile:
    top_k: int = 6
    min_score: float = 0.5
    languages: list[str] | None = None
    document_types: list[str] | None = None
    audience: str = "customer"
    # Categoria = folderul din galaxy-bank-knowledge (derivata in DB din
    # knowledge_documents.sursa, migratia 0033) — ingusteaza cautarea la un
    # subiect, cand agentul stie deja despre ce e vorba (ex. credit_intent).
    categories: list[str] | None = None


DEFAULT_PROFILE = RetrievalProfile()


class RetrievalService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        knowledge_repository: KnowledgeRepository,
        embedding_cache_repository: EmbeddingCacheRepository,
        embedding_key: str,
    ) -> None:
        self._embeddings = embedding_provider
        self._knowledge = knowledge_repository
        self._cache = embedding_cache_repository
        self._embedding_key = embedding_key

    async def search(self, query: str, profile: RetrievalProfile = DEFAULT_PROFILE) -> list[KnowledgeChunkHit]:
        cache_key = query_cache_key(self._embedding_key, query)
        cached = await self._cache.get_query_embedding(cache_key)

        if cached is not None:
            query_embedding = cached
        else:
            [query_embedding] = await self._embeddings.embed([query])
            await self._cache.put_query_embedding(cache_key, self._embedding_key, query_embedding)

        return await self._knowledge.search(
            embedding_key=self._embedding_key,
            query_embedding=query_embedding,
            languages=profile.languages,
            document_types=profile.document_types,
            audience=profile.audience,
            top_k=profile.top_k,
            min_score=profile.min_score,
            # Textul brut al interogarii, nu embedding-ul — RPC-ul il foloseste
            # doar ca plasa de siguranta full-text (migratia 0033), separat de
            # similaritatea vectoriala de mai sus.
            query_text=query,
            categories=profile.categories,
        )

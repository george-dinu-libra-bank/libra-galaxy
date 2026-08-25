from dataclasses import dataclass, field

import pytest

from app.rag.retrieval import RetrievalProfile, RetrievalService


@dataclass
class EmbeddingProviderFals:
    apeluri: list[list[str]] = field(default_factory=list)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.apeluri.append(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]


@dataclass
class EmbeddingCacheFals:
    async def get_query_embedding(self, query_hash: str):
        return None

    async def put_query_embedding(self, query_hash: str, embedding_key: str, embedding) -> None:
        pass


@dataclass
class KnowledgeRepositoryFals:
    apeluri: list[dict] = field(default_factory=list)

    async def search(self, **kwargs):
        self.apeluri.append(kwargs)
        return []


@pytest.mark.anyio
async def test_search_forwards_query_text_and_categories_to_repository():
    """query_text (plasa de siguranta full-text) si categories (filtru de
    izolare pe folder) trebuie sa ajunga neschimbate la repository — vezi
    migratia 0027_rag_categorie_si_cautare_hibrida.sql."""
    knowledge = KnowledgeRepositoryFals()
    service = RetrievalService(EmbeddingProviderFals(), knowledge, EmbeddingCacheFals(), "test-key")
    profile = RetrievalProfile(categories=["credite"])

    await service.search("ce conditii am pentru credit ipotecar", profile)

    assert len(knowledge.apeluri) == 1
    apel = knowledge.apeluri[0]
    assert apel["query_text"] == "ce conditii am pentru credit ipotecar"
    assert apel["categories"] == ["credite"]


@pytest.mark.anyio
async def test_search_without_categories_passes_none():
    knowledge = KnowledgeRepositoryFals()
    service = RetrievalService(EmbeddingProviderFals(), knowledge, EmbeddingCacheFals(), "test-key")

    await service.search("intrebare generala")

    assert knowledge.apeluri[0]["categories"] is None

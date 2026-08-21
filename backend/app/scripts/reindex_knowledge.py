"""Reindexeaza galaxy-bank-knowledge/ in knowledge_chunks — incremental, prin plan_reindex.

Local:  python -m app.scripts.reindex_knowledge (din backend/, cu venv activ si .env completat).
Docker: docker compose exec backend python -m app.scripts.reindex_knowledge

Folderul sursa vine din settings.knowledge_dir_path — LIBRA_KNOWLEDGE_DIR daca e
setat, altfel repo_root/galaxy-bank-knowledge (calculat, nu presupus din adancimea
fisierului, ca sa nu depinda tacit de structura containerului).
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.infrastructure.supabase_client import get_service_client
from app.providers.foundry import MicrosoftFoundryEmbeddingProvider
from app.rag.indexing import chunk_document, embedding_cache_key, plan_reindex
from app.rag.registry import load_knowledge_documents
from app.repositories.embedding_cache_repository import EmbeddingCacheRepository
from app.repositories.knowledge_repository import KnowledgeRepository

EMBEDDING_BATCH_SIZE = 16


async def reindex() -> None:
    settings = get_settings()
    client = get_service_client()

    knowledge_repo = KnowledgeRepository(client)
    cache_repo = EmbeddingCacheRepository(client)
    embeddings = MicrosoftFoundryEmbeddingProvider(settings)

    documents = load_knowledge_documents(settings.knowledge_dir_path)
    print(f"{len(documents)} documente gasite in {settings.knowledge_dir_path}")

    existing_ids = await knowledge_repo.existing_chunk_ids(settings.embedding_key)
    desired_chunks = []
    chunk_to_document: dict[str, tuple[str, int, str | None]] = {}

    for document in documents:
        await knowledge_repo.upsert_document(
            document.document_id, document.version, document.source_path, document.document_type,
            document.language, document.checksum, document.audience,
        )
        chunks = chunk_document(document)
        desired_chunks.extend(chunks)
        for chunk in chunks:
            chunk_to_document[chunk.chunk_id] = (document.document_id, document.version, chunk.section)

    plan = plan_reindex(desired_chunks, existing_ids)
    print(f"de embedat: {len(plan.to_embed)}, refolosite: {len(plan.to_reuse_ids)}, sterse: {len(plan.to_delete_ids)}")

    rows_to_upsert = []
    for start in range(0, len(plan.to_embed), EMBEDDING_BATCH_SIZE):
        batch = plan.to_embed[start : start + EMBEDDING_BATCH_SIZE]
        texts = [chunk.text for chunk in batch]

        cached_vectors = [
            await cache_repo.get_chunk_embedding(embedding_cache_key(settings.embedding_key, text)) for text in texts
        ]
        missing_indexes = [i for i, vector in enumerate(cached_vectors) if vector is None]

        if missing_indexes:
            fresh_vectors = await embeddings.embed([texts[i] for i in missing_indexes])
            for i, vector in zip(missing_indexes, fresh_vectors):
                cached_vectors[i] = vector
                await cache_repo.put_chunk_embedding(embedding_cache_key(settings.embedding_key, texts[i]), vector)

        for chunk, vector in zip(batch, cached_vectors):
            document_id, version, section = chunk_to_document[chunk.chunk_id]
            rows_to_upsert.append(
                {
                    "chunk_id": chunk.chunk_id, "document_id": document_id, "versiune": version,
                    "sectiune": section, "continut": chunk.text, "embedding": vector, "metadata": {},
                }
            )

    await knowledge_repo.upsert_chunks(settings.embedding_key, rows_to_upsert)
    await knowledge_repo.delete_chunks(settings.embedding_key, list(plan.to_delete_ids))

    print("Reindexare terminata.")


if __name__ == "__main__":
    asyncio.run(reindex())

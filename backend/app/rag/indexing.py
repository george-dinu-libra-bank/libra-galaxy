"""Reindexare incrementala (docs/AI_ARCHITECTURE.md #7, PATTERN_ADOPTION.md).

`plan_reindex` e o functie pura: primeste chunk-urile dorite si id-urile deja
indexate pentru o cheie de embedding, si spune ce trebuie pastrat, embedat sau
sters — fara baza de date, fara provider, testabila direct.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.rag.chunking import Chunk, fixed_window_chunk, section_aware_chunk
from app.rag.registry import KnowledgeDocument

_SECTION_AWARE_TYPES = {"procedură", "produs", "faq", "referinta", "index", "politica"}


@dataclass(frozen=True)
class ReindexPlan:
    to_embed: list[Chunk]
    to_reuse_ids: set[str]
    to_delete_ids: set[str]


def chunk_document(document: KnowledgeDocument) -> list[Chunk]:
    if document.document_type in _SECTION_AWARE_TYPES:
        chunks = section_aware_chunk(document.document_id, document.version, document.content)
        if chunks:
            return chunks
    return fixed_window_chunk(document.document_id, document.version, document.content)


def plan_reindex(desired_chunks: list[Chunk], existing_chunk_ids: set[str]) -> ReindexPlan:
    desired_ids = {chunk.chunk_id for chunk in desired_chunks}

    to_embed = [chunk for chunk in desired_chunks if chunk.chunk_id not in existing_chunk_ids]
    to_reuse_ids = desired_ids & existing_chunk_ids
    to_delete_ids = existing_chunk_ids - desired_ids

    return ReindexPlan(to_embed=to_embed, to_reuse_ids=to_reuse_ids, to_delete_ids=to_delete_ids)


def embedding_cache_key(embedding_key: str, text: str) -> str:
    payload = f"{embedding_key}\0{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def query_cache_key(embedding_key: str, query: str) -> str:
    return embedding_cache_key(embedding_key, query.strip().casefold())

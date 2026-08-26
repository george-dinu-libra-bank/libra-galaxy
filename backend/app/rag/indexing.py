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


@dataclass(frozen=True)
class ReindexPlan:
    to_embed: list[Chunk]
    to_reuse_ids: set[str]
    to_delete_ids: set[str]


def chunk_document(document: KnowledgeDocument) -> list[Chunk]:
    """Alege strategia dupa forma reala a continutului — cate sectiuni `##`
    are — nu dupa o lista fixa de tip_document. O lista fixa e fragila: un
    tip nou (sau o singura diacritica lipsa, cum a fost cazul cu "politica"
    vs "politică" — verificat live ca afecta toate cele 11 documente cu acel
    tip) face tacut un document sa piarda chunking-ul pe sectiuni, fara nicio
    eroare care sa semnaleze asta.

    Sectiunile sunt de incredere doar cand exista o structura REALA (2+
    sectiuni): cu 0 sau 1 titlu, section_aware_chunk ar intoarce oricum un
    singur chunk care acopera tot documentul — nu mai bun decat fereastra
    fixa, si fara avantajul de a imparti proza lunga in bucati digerabile."""
    sectioned = section_aware_chunk(document.document_id, document.version, document.content)
    if len(sectioned) > 1:
        return sectioned
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

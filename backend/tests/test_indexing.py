from app.rag.indexing import chunk_document, plan_reindex
from app.rag.registry import KnowledgeDocument


def _document(document_type: str, content: str) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id="grupuri/doc",
        source_path="grupuri/doc.md",
        language="ro",
        document_type=document_type,
        version=1,
        checksum="abc",
        content=content,
    )


def test_chunk_document_uses_section_aware_for_politica_cu_diacritice():
    """Toate documentele din galaxy-bank-knowledge folosesc 'politică' (cu
    diacritice) — verificat live cu grep, 11 din 11. _SECTION_AWARE_TYPES avea
    'politica' (fara diacritice), care nu se potrivea niciodata, deci aceste
    documente cadeau tacit pe fixed_window_chunk in loc de sectiuni citabile."""
    content = "# Titlu\n\n## Sectiunea unu\ntext unu\n\n## Sectiunea doi\ntext doi\n"
    chunks = chunk_document(_document("politică", content))

    sections = [chunk.section for chunk in chunks]
    assert "Sectiunea unu" in sections
    assert "Sectiunea doi" in sections


def test_chunk_document_falls_back_to_fixed_window_for_unlisted_types():
    content = " ".join(f"cuvant{i}" for i in range(50))
    chunks = chunk_document(_document("educatie-financiara", content))

    assert all(chunk.section is None for chunk in chunks)


def test_plan_reindex_reuses_unchanged_and_deletes_stale():
    # Fara titlu de nivel 1: "# Titlu" s-ar potrivi si el pe _HEADING_RE
    # (1-3 #), devenind propria sa sectiune — testul vrea exact 2 chunk-uri.
    content = "## A\ntext a\n\n## B\ntext b\n"
    desired = chunk_document(_document("politică", content))
    existing_ids = {desired[0].chunk_id, "chunk-vechi-disparut"}

    plan = plan_reindex(desired, existing_ids)

    assert plan.to_reuse_ids == {desired[0].chunk_id}
    assert plan.to_delete_ids == {"chunk-vechi-disparut"}
    assert [chunk.chunk_id for chunk in plan.to_embed] == [desired[1].chunk_id]

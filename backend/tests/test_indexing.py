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


def test_chunk_document_uses_section_aware_when_content_has_real_sections():
    """chunk_document decide dupa continut (2+ sectiuni ##), nu dupa
    tip_document — un tip_document facut la intamplare tot primeste chunking
    pe sectiuni daca textul chiar le are."""
    content = "# Titlu\n\n## Sectiunea unu\ntext unu\n\n## Sectiunea doi\ntext doi\n"
    chunks = chunk_document(_document("tip-inventat-oarecare", content))

    sections = [chunk.section for chunk in chunks]
    assert "Sectiunea unu" in sections
    assert "Sectiunea doi" in sections


def test_chunk_document_covers_ghid_operational_type():
    """Regresie concreta: galaxy-bank-knowledge/grupuri/galaxy-bank-creare-si-
    administrare-grup.md are tip_document 'ghid-operațional' si sectiuni ##
    reale, dar vechiul _SECTION_AWARE_TYPES (o lista fixa) nu-l acoperea —
    cadea tacit pe fereastra fixa. Acum orice tip cu structura reala e prins."""
    content = "## Crearea unui grup\ntext\n\n## Condiții de eligibilitate\ntext\n"
    chunks = chunk_document(_document("ghid-operațional", content))

    sections = [chunk.section for chunk in chunks]
    assert "Crearea unui grup" in sections
    assert "Condiții de eligibilitate" in sections


def test_chunk_document_falls_back_to_fixed_window_without_real_sections():
    # Un singur titlu (sau niciunul) nu inseamna structura reala — fereastra
    # fixa imparte proza lunga in bucati digerabile, spre deosebire de un
    # singur chunk urias care ar acoperi tot documentul.
    content = " ".join(f"cuvant{i}" for i in range(50))
    chunks = chunk_document(_document("politică", content))

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

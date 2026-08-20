from app.rag.chunking import chunk_id_for, fixed_window_chunk, section_aware_chunk


def test_section_aware_chunk_splits_on_headings():
    content = "# Titlu\n\n## Sectiunea unu\ntext unu\n\n## Sectiunea doi\ntext doi\n"
    chunks = section_aware_chunk("doc", 1, content)

    sections = [chunk.section for chunk in chunks]
    assert "Sectiunea unu" in sections
    assert "Sectiunea doi" in sections


def test_chunk_id_changes_when_text_changes():
    id_a = chunk_id_for("doc", 1, 0, "text original")
    id_b = chunk_id_for("doc", 1, 0, "text modificat")
    assert id_a != id_b


def test_chunk_id_stable_for_same_input():
    id_a = chunk_id_for("doc", 1, 0, "acelasi text")
    id_b = chunk_id_for("doc", 1, 0, "acelasi text")
    assert id_a == id_b


def test_fixed_window_chunk_respects_window_size():
    content = " ".join(f"cuvant{i}" for i in range(400))
    chunks = fixed_window_chunk("doc", 1, content, window_words=150, overlap_words=25)

    assert len(chunks) > 1
    assert all(len(chunk.text.split()) <= 150 for chunk in chunks)


def test_fixed_window_chunk_empty_content():
    assert fixed_window_chunk("doc", 1, "") == []

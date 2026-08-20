from app.rag.chunking import Chunk
from app.rag.indexing import plan_reindex


def _chunk(chunk_id: str, text: str = "text") -> Chunk:
    return Chunk(chunk_id=chunk_id, section=None, text=text, position=0)


def test_unchanged_chunks_are_reused_not_reembedded():
    desired = [_chunk("a"), _chunk("b")]
    existing = {"a", "b"}

    plan = plan_reindex(desired, existing)

    assert plan.to_embed == []
    assert plan.to_reuse_ids == {"a", "b"}
    assert plan.to_delete_ids == set()


def test_new_chunk_is_scheduled_for_embedding():
    desired = [_chunk("a"), _chunk("b")]
    existing = {"a"}

    plan = plan_reindex(desired, existing)

    assert [chunk.chunk_id for chunk in plan.to_embed] == ["b"]
    assert plan.to_reuse_ids == {"a"}


def test_removed_chunk_is_scheduled_for_deletion():
    desired = [_chunk("a")]
    existing = {"a", "b"}

    plan = plan_reindex(desired, existing)

    assert plan.to_delete_ids == {"b"}


def test_partial_document_edit_only_reembeds_changed_chunk():
    # Editarea unei sectiuni schimba doar id-ul acelui chunk — restul documentului
    # ramane neschimbat si nu trebuie reembedat.
    desired = [_chunk("unchanged"), _chunk("edited-v2")]
    existing = {"unchanged", "edited-v1"}

    plan = plan_reindex(desired, existing)

    assert [chunk.chunk_id for chunk in plan.to_embed] == ["edited-v2"]
    assert plan.to_reuse_ids == {"unchanged"}
    assert plan.to_delete_ids == {"edited-v1"}


def test_changing_embedding_key_forces_full_rebuild():
    # O cheie de embedding noua inseamna existing_chunk_ids gol pentru cheia respectiva —
    # totul se re-embedeaza, nimic nu se amesteca cu spatiul vechi de vectori.
    desired = [_chunk("a"), _chunk("b")]
    existing_for_new_key: set[str] = set()

    plan = plan_reindex(desired, existing_for_new_key)

    assert {chunk.chunk_id for chunk in plan.to_embed} == {"a", "b"}
    assert plan.to_reuse_ids == set()

from app.memory.compression import MAX_SUMMARY_CHARS, condense_message, fold_messages_into_summary, preview
from app.repositories.message_repository import Message


def _message(sequence: int, role: str, text: str) -> Message:
    return Message(id=f"m{sequence}", conversation_id="c1", sequence=sequence, role=role, text=text)


def test_preview_truncates_long_text():
    long_text = "a" * 500
    result = preview(long_text, 100)
    assert len(result) == 100
    assert result.endswith("…")


def test_preview_keeps_short_text_unchanged():
    assert preview("mesaj scurt", 100) == "mesaj scurt"


def test_condense_message_labels_role():
    assert condense_message(_message(1, "user", "buna")).startswith("UTILIZATOR:")
    assert condense_message(_message(1, "assistant", "buna")).startswith("ASISTENT:")


def test_fold_messages_appends_to_existing_summary():
    existing = "UTILIZATOR: mesaj vechi"
    new_messages = [_message(2, "assistant", "raspuns nou")]

    result = fold_messages_into_summary(existing, new_messages)

    assert "mesaj vechi" in result
    assert "raspuns nou" in result


def test_fold_messages_with_no_new_messages_returns_unchanged():
    existing = "rezumat existent"
    assert fold_messages_into_summary(existing, []) == existing


def test_fold_messages_truncates_to_max_chars():
    existing = "x" * (MAX_SUMMARY_CHARS - 10)
    new_messages = [_message(2, "user", "y" * 100)]

    result = fold_messages_into_summary(existing, new_messages, max_chars=MAX_SUMMARY_CHARS)

    assert len(result) <= MAX_SUMMARY_CHARS
    # Pastreaza sfarsitul (cele mai recente informatii), nu inceputul.
    assert "y" in result

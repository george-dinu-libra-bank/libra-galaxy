import pytest

from app.memory.extraction import extract_memory


@pytest.mark.parametrize(
    "text,expected_type",
    [
        ("Prefer sa vorbim in engleza de-acum incolo.", "preferinta"),
        ("I prefer short answers.", "preferinta"),
        ("Numeste-ma Florin de-acum incolo.", "preferinta"),
        ("Please call me Alex.", "preferinta"),
        ("Aminteste-ti ca vreau un rezumat lunar.", "intentie_declarata"),
        ("Remember that I check my spending every Friday.", "intentie_declarata"),
    ],
)
def test_matched_phrases_extract_expected_type(text, expected_type):
    result = extract_memory(text)
    assert result is not None
    assert result.memory_type == expected_type
    assert result.content


def test_unmatched_text_extracts_nothing():
    assert extract_memory("Ce vreme e afara?") is None


@pytest.mark.parametrize(
    "text",
    [
        "Prefer sa pastrez 500 RON in cont in fiecare luna.",
        "I prefer to keep 200 EUR aside.",
        "Numeste-ma cand ajung la 1000 lei economii.",
        "Prefer sa platesc din contul RO49LIBR1B310075938400.",
    ],
)
def test_content_resembling_banking_state_is_never_extracted(text):
    # Chiar daca fraza se potriveste cu un tipar de preferinta, orice continut
    # cu cifre/valuta/IBAN trebuie respins — memoria conversationala nu poate
    # deveni niciodata stare bancara (CLAUDE.md #24/#25).
    assert extract_memory(text) is None


def test_diacritics_do_not_change_classification():
    with_diacritics = extract_memory("Prefer să vorbim în română.")
    without_diacritics = extract_memory("Prefer sa vorbim in romana.")
    assert with_diacritics is not None
    assert without_diacritics is not None
    assert with_diacritics.memory_type == without_diacritics.memory_type == "preferinta"

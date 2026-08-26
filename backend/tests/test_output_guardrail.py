from app.orchestration.output_guardrail import redact


def test_iban_passes_through_unmasked():
    # Decizie explicita (GUARDRAILS.md #12): IBAN-ul propriu nu mai e mascat,
    # nici la sursa (banking_tools.py), nici aici — nu e un secret ca un CVV.
    text = "Contul tau are IBAN-ul RO49AAAA1B31007593840000, cu soldul de 100 RON."
    assert redact(text) == text


def test_card_number_gets_masked():
    # Niciun tool nu intoarce azi un numar de card (GUARDRAILS.md #13) — testul
    # verifica doar plasa de siguranta defensiva.
    text = "Cardul tau are numarul 4111111111111111, verifica te rog."
    result = redact(text)

    assert "4111111111111111" not in result
    assert result.endswith("1111, verifica te rog.")
    assert "•" in result


def test_grouped_card_number_gets_masked():
    text = "Numarul cardului este 4111 1111 1111 1111."
    result = redact(text)

    assert "4111 1111 1111 1111" not in result
    assert "•" in result


def test_secret_labels_get_hidden():
    assert redact("parola: abc123") == "parola: [ascuns]"
    assert redact("CVV: 123") == "CVV: [ascuns]"
    assert redact("api_key=sk-test-xyz") == "api_key: [ascuns]"
    assert redact("token: eyJhbGciOi") == "token: [ascuns]"


def test_normal_answer_passes_through_unchanged():
    text = "Ai cheltuit 340 RON pe abonamente luna asta, in principal Netflix si Spotify."
    assert redact(text) == text


def test_answer_without_secrets_or_iban_is_untouched():
    text = "Persoana care ti-a trimis cei mai multi bani este Preda Cristian."
    assert redact(text) == text

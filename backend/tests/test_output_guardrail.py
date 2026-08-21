from app.orchestration.output_guardrail import redact


def test_iban_gets_masked():
    text = "Contul tau are IBAN-ul RO49AAAA1B31007593840000, cu soldul de 100 RON."
    result = redact(text)

    assert "RO49AAAA1B31007593840000" not in result
    assert result.startswith("Contul tau are IBAN-ul RO49")
    assert result.endswith("0000, cu soldul de 100 RON.")
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

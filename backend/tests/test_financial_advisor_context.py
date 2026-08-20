from app.agents.financial_advisor import _sarcina_cu_context
from app.context.builder import ContextBuilder, ContextSource


def test_recent_conversation_is_prepended_to_the_task():
    builder = ContextBuilder()
    sections = [
        builder.add(
            ContextSource.RECENT_CONVERSATION, "Conversatia recenta",
            "user: cine mi-a trimis cei mai multi bani?\nassistant: Preda Cristian, 1000000000.0 RON.",
        )
    ]
    context = builder.build(sections)

    sarcina = _sarcina_cu_context("dar cel mai mic?", context)

    assert "Preda Cristian" in sarcina
    assert sarcina.endswith("Intrebarea curenta: dar cel mai mic?")


def test_no_recent_conversation_falls_back_to_plain_text():
    context = ContextBuilder().build([])

    assert _sarcina_cu_context("cat am in cont?", context) == "cat am in cont?"

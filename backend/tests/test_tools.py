from uuid import uuid4

from app.tools.financial_tools import construieste_tools


def test_tool_urile_nu_expun_user_id_catre_model() -> None:
    tools = construieste_tools(service=None, user_id=uuid4())

    nume = {tool.name for tool in tools}
    assert nume == {"obtine_sold", "obtine_cashflow_lunar", "obtine_tranzactii_recente"}

    for tool in tools:
        proprietati = tool.input_schema.get("properties", {})
        assert "user_id" not in proprietati
        assert "id_user" not in proprietati

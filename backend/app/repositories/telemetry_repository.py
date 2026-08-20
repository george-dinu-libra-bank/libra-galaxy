from __future__ import annotations

from supabase import Client


class TelemetryRepository:
    """Jurnal AI fara continut de mesaj (docs/SECURITY.md #3) — identificatori, durate, contoare."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def record_run(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        agent_id: str,
        intent: str,
        risk_level: str,
        prompt_version: str,
        deployment: str,
        latency_ms: int,
        tool_count: int,
        retrieved_chunks: int,
        context_chars: int,
        success: bool,
        error_code: str | None,
    ) -> str | None:
        result = (
            self._client.table("agent_runs")
            .insert(
                {
                    "id_user": user_id,
                    "id_conversation": conversation_id,
                    "id_agent": agent_id,
                    "intentie": intent,
                    "nivel_risc": risk_level,
                    "versiune_prompt": prompt_version,
                    "deployment": deployment,
                    "latenta_ms": latency_ms,
                    "numar_tool_uri": tool_count,
                    "fragmente_regasite": retrieved_chunks,
                    "context_caractere": context_chars,
                    "succes": success,
                    "cod_eroare": error_code,
                }
            )
            .execute()
        )
        return result.data[0]["id"] if result.data else None

    def record_tool_invocation(
        self, *, run_id: str, tool_name: str, success: bool, duration_ms: int, reason: str
    ) -> None:
        if not run_id:
            return
        self._client.table("tool_invocations").insert(
            {
                "id_run": run_id,
                "nume_tool": tool_name,
                "succes": success,
                "durata_ms": duration_ms,
                "motiv_selectie": reason,
            }
        ).execute()

    def record_usage(
        self,
        *,
        feature: str,
        agent_id: str | None,
        deployment: str | None,
        environment: str,
        tokens_in: int,
        tokens_out: int,
        tokens_cached: int,
        estimated_cost_usd: float,
    ) -> None:
        self._client.table("ai_usage_records").insert(
            {
                "feature": feature,
                "id_agent": agent_id,
                "deployment": deployment,
                "environment": environment,
                "tokeni_intrare": tokens_in,
                "tokeni_iesire": tokens_out,
                "tokeni_cache": tokens_cached,
                "cost_estimat_usd": estimated_cost_usd,
            }
        ).execute()

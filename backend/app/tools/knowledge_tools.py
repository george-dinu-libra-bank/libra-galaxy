from __future__ import annotations

from app.core.security import PERMISSION_ASSISTANT_USE, Principal
from app.rag.retrieval import RetrievalProfile, RetrievalService
from app.tools.base import RiskLevel, SideEffect, ToolDefinition


def build_knowledge_tools(retrieval_service: RetrievalService) -> list[ToolDefinition]:
    async def search_bank_knowledge(principal: Principal, args: dict) -> dict:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"hits": []}

        profile = RetrievalProfile(languages=[principal.locale] if principal.locale else None)
        hits = await retrieval_service.search(query, profile)

        return {
            "hits": [
                {
                    "document_id": hit.document_id,
                    "section": hit.section,
                    "text": hit.text,
                    "score": hit.score,
                }
                for hit in hits
            ]
        }

    return [
        ToolDefinition(
            name="search_bank_knowledge",
            description="Cauta in baza de cunostinte a bancii (politici, produse, proceduri, FAQ).",
            callback=search_bank_knowledge,
            allowed_agents=frozenset({"document_intelligence"}),
            required_permissions=frozenset({PERMISSION_ASSISTANT_USE}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        )
    ]

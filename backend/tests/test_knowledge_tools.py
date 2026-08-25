from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from app.core.security import Principal
from app.rag.retrieval import RetrievalProfile
from app.tools.knowledge_tools import build_knowledge_tools

UTILIZATOR = Principal(user_id=str(uuid4()), role="customer", permissions={"assistant:use"})


@dataclass
class RetrievalServiceFals:
    profiluri_primite: list[RetrievalProfile] = field(default_factory=list)

    async def search(self, query: str, profile: RetrievalProfile):
        self.profiluri_primite.append(profile)
        return []


@pytest.mark.anyio
async def test_categorie_hint_narrows_the_retrieval_profile():
    retrieval = RetrievalServiceFals()
    tool = build_knowledge_tools(retrieval)[0]

    await tool.callback(UTILIZATOR, {"query": "ce conditii am", "categorie_hint": "credite"})

    assert retrieval.profiluri_primite[0].categories == ["credite"]


@pytest.mark.anyio
async def test_without_categorie_hint_no_category_filter_is_applied():
    retrieval = RetrievalServiceFals()
    tool = build_knowledge_tools(retrieval)[0]

    await tool.callback(UTILIZATOR, {"query": "ce comisioane am"})

    assert retrieval.profiluri_primite[0].categories is None


@pytest.mark.anyio
async def test_empty_query_never_reaches_retrieval():
    retrieval = RetrievalServiceFals()
    tool = build_knowledge_tools(retrieval)[0]

    result = await tool.callback(UTILIZATOR, {"query": "  "})

    assert result == {"hits": []}
    assert retrieval.profiluri_primite == []

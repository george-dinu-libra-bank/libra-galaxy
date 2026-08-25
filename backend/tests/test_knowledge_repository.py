from types import SimpleNamespace

import pytest
from postgrest.exceptions import APIError

from app.core.errors import RetrievalError
from app.repositories.knowledge_repository import KnowledgeRepository


class _RpcApelFals:
    def __init__(self, client: "ClientFals", payload: dict) -> None:
        self._client = client
        self._payload = payload

    def execute(self):
        self._client.payloaduri.append(self._payload)
        if self._client.esueaza_cu_pgrst202 and "p_query_text" in self._payload:
            raise APIError({"code": "PGRST202", "message": "functia nu exista inca"})
        return SimpleNamespace(data=self._client.randuri)


class ClientFals:
    """Migratia 0027 nu e inca aplicata: RPC-ul cu p_query_text/p_categories
    nu exista, dar cel vechi (fara ele) tot merge."""

    def __init__(self, esueaza_cu_pgrst202: bool, randuri: list[dict] | None = None) -> None:
        self.esueaza_cu_pgrst202 = esueaza_cu_pgrst202
        self.randuri = randuri or []
        self.payloaduri: list[dict] = []

    def rpc(self, nume: str, payload: dict) -> _RpcApelFals:
        return _RpcApelFals(self, payload)


_RAND_EXEMPLU = {
    "chunk_id": "c1", "document_id": "d1", "versiune": 1,
    "sectiune": None, "continut": "text", "metadata": {}, "scor": 0.7,
}


@pytest.mark.anyio
async def test_search_uses_full_payload_when_the_new_rpc_exists():
    client = ClientFals(esueaza_cu_pgrst202=False, randuri=[_RAND_EXEMPLU])
    repo = KnowledgeRepository(client)  # type: ignore[arg-type]

    hits = await repo.search(
        embedding_key="k", query_embedding=[0.1], languages=None, document_types=None,
        audience="customer", top_k=6, min_score=0.5, query_text="intrebare", categories=["credite"],
    )

    assert len(hits) == 1
    assert len(client.payloaduri) == 1
    assert client.payloaduri[0]["p_query_text"] == "intrebare"
    assert client.payloaduri[0]["p_categories"] == ["credite"]


@pytest.mark.anyio
async def test_search_falls_back_to_legacy_rpc_when_migration_not_yet_applied():
    """PGRST202 (functie negasita) inseamna ca migratia 0027 inca nu a fost
    rulata — cautarea trebuie sa reincerce fara p_query_text/p_categories, nu
    sa pice complet (raportat/reprodus live: exact asta se intampla inainte
    de acest fix, contra proiectului Supabase real, neactualizat inca)."""
    client = ClientFals(esueaza_cu_pgrst202=True, randuri=[_RAND_EXEMPLU])
    repo = KnowledgeRepository(client)  # type: ignore[arg-type]

    hits = await repo.search(
        embedding_key="k", query_embedding=[0.1], languages=None, document_types=None,
        audience="customer", top_k=6, min_score=0.5, query_text="intrebare", categories=["credite"],
    )

    assert len(hits) == 1
    # Doua incercari: cea noua (esuata cu PGRST202), apoi cea veche (reusita).
    assert len(client.payloaduri) == 2
    assert "p_query_text" in client.payloaduri[0]
    assert "p_query_text" not in client.payloaduri[1]
    assert "p_categories" not in client.payloaduri[1]


@pytest.mark.anyio
async def test_search_raises_retrieval_error_for_other_api_errors():
    class ClientEroareAlta:
        def rpc(self, nume, payload):
            class _Apel:
                def execute(self):
                    raise APIError({"code": "PGRST000", "message": "eroare neasteptata"})

            return _Apel()

    repo = KnowledgeRepository(ClientEroareAlta())  # type: ignore[arg-type]

    with pytest.raises(RetrievalError):
        await repo.search(
            embedding_key="k", query_embedding=[0.1], languages=None, document_types=None,
            audience="customer", top_k=6, min_score=0.5,
        )

from uuid import UUID

from anyio import to_thread
from supabase import Client

CAMPURI = "id_tranzactie,categorie"


class CategorieManualaRepository:
    """Suprascrieri de categorie confirmate de utilizator (migratia 0036) —
    separat de categorizeaza() (tools/categorii_tranzactii.py), care ramane
    implicitul determinist cand nu exista nicio suprascriere."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def pentru_tranzactii(self, tranzactie_ids: list[UUID]) -> dict[str, str]:
        """Categoria manuala, cheie fiind id_tranzactie (ca text) — doar pentru
        tranzactiile cerute, ca sa nu se aduca intreaga tabela la fiecare cerere."""
        if not tranzactie_ids:
            return {}

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("categorii_manuale_tranzactii")
                .select(CAMPURI)
                .in_("id_tranzactie", [str(id_) for id_ in tranzactie_ids])
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return {str(rand["id_tranzactie"]): rand["categorie"] for rand in randuri}

    async def seteaza(self, id_tranzactie: UUID, id_user: UUID, categorie: str) -> None:
        """Upsert — a doua confirmare pe aceeasi tranzactie inlocuieste categoria,
        nu adauga un rand nou (primary key = id_tranzactie)."""

        def scrie() -> None:
            self._client.table("categorii_manuale_tranzactii").upsert(
                {"id_tranzactie": str(id_tranzactie), "id_user": str(id_user), "categorie": categorie}
            ).execute()

        await to_thread.run_sync(scrie)

from uuid import UUID

from anyio import to_thread
from supabase import Client

# Creditele care tin clientul legat de banca. Aceleasi valori pe care le
# foloseste credit_service.py cand refuza o rambursare pe un credit inchis.
CREDITE_IN_DERULARE = ("activ", "restant")

CAMPURI_CERERE = "id,status,motiv,creat_la,decis_la,motiv_refuz"


class ProfileRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def get_owned_profile(self, user_id: UUID) -> dict | None:
        def query() -> dict | None:
            response = (
                self._client.table("profiles")
                .select("id,nume,cnp,telefon,email,iban_cont,creat_la,modificat_la")
                .eq("id", str(user_id))
                .maybe_single()
                .execute()
            )
            return response.data

        return await to_thread.run_sync(query)

    # -- ce il tine pe client legat de banca -------------------------------

    async def numara_credite_in_derulare(self, user_id: UUID) -> int:
        def query() -> int:
            response = (
                self._client.table("credite")
                .select("id")
                .eq("id_user", str(user_id))
                .in_("status", list(CREDITE_IN_DERULARE))
                .execute()
            )
            return len(response.data or [])

        return await to_thread.run_sync(query)

    async def conturi_cu_sold(self, user_id: UUID) -> list[dict]:
        """Conturile cu bani in ele. Un sold negativ conteaza si el: inseamna
        ca datoreaza, nu ca poate pleca."""

        def query() -> list[dict]:
            response = (
                self._client.table("conturi_bancare")
                .select("id,nume,sold,valuta")
                .eq("id_user", str(user_id))
                .neq("sold", 0)
                .execute()
            )
            return response.data or []

        return await to_thread.run_sync(query)

    # -- cererea de stergere ------------------------------------------------

    async def cerere_stergere_deschisa(self, user_id: UUID) -> dict | None:
        def query() -> dict | None:
            response = (
                self._client.table("cereri_stergere_cont")
                .select(CAMPURI_CERERE)
                .eq("id_utilizator", str(user_id))
                .eq("status", "in_asteptare")
                # `limit(1)` + lista, nu `maybe_single()`: maybe_single arunca
                # daca gaseste doua randuri, iar un index unic partial care
                # cedeaza n-are de ce sa scoata 500 pe o pagina de setari.
                .limit(1)
                .execute()
            )
            randuri = response.data or []
            return randuri[0] if randuri else None

        return await to_thread.run_sync(query)

    async def creeaza_cerere_stergere(self, user_id: UUID, motiv: str | None) -> dict:
        def query() -> dict:
            response = (
                self._client.table("cereri_stergere_cont")
                .insert({"id_utilizator": str(user_id), "motiv": motiv})
                .execute()
            )
            return response.data[0]

        return await to_thread.run_sync(query)

    async def retrage_cerere_stergere(self, user_id: UUID, id_cerere: str) -> dict | None:
        def query() -> dict | None:
            response = (
                self._client.table("cereri_stergere_cont")
                .update({"status": "retrasa"})
                .eq("id", id_cerere)
                .eq("id_utilizator", str(user_id))
                .eq("status", "in_asteptare")
                .execute()
            )
            randuri = response.data or []
            return randuri[0] if randuri else None

        return await to_thread.run_sync(query)

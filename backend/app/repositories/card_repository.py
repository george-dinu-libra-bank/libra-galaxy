from uuid import UUID

from anyio import to_thread
from supabase import Client

# Numarul complet de card si CVV-ul nu ies niciodata catre un agent — nici
# macar nu sunt citite aici, ca sa nu poata scapa printr-o extindere gresita
# mai tarziu (GUARDRAILS.md #13). Data expirarii si stilul sunt sigure pentru
# tools/card_tools.py — nu identifica singure cardul, spre deosebire de numar/CVV.
# Coloanele trebuie sa existe in baza reala, nu doar in migrarile din repo:
# schema din cloud a luat-o inainte (vezi conturi_bancare, absent din migrari).
# `sold_curent` nu se citeste: e coloana moarta. Nicio functie SQL din proiect
# nu o scrie, iar in baza reala e 0 pe toate cardurile. Banii stau pe cont.
CAMPURI = "id,id_cont,is_blocked,creat_la,data_expirare,card_style,tip,limita_zilnica"


class CardRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def ale_utilizatorului(self, user_id: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("carduri")
                .select(CAMPURI)
                .eq("id_user", str(user_id))
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

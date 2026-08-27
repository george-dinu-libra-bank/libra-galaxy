"""Sesizarile clientului: trimiterea si raspunsul administratorului."""

from dataclasses import dataclass

from app.core.errors import ResourceNotFoundError, ValidationError
from app.repositories.admin_repository import AnalizaRepository
from app.repositories.suport_repository import SuportRepository

MIN_REZUMAT = 10
MAX_REZUMAT = 4000
STATUSURI = ("deschisa", "in_lucru", "rezolvata")


@dataclass(slots=True)
class RezultatTrimitere:
    id: str
    creata_acum: bool


class SuportService:
    def __init__(self, sesizari: SuportRepository, notificari: AnalizaRepository) -> None:
        self._sesizari = sesizari
        self._notificari = notificari

    async def trimite(
        self, user_id: str, subiect: str, rezumat: str, context: dict | None = None
    ) -> RezultatTrimitere:
        subiect = (subiect or "").strip()
        rezumat = (rezumat or "").strip()

        if len(subiect) < 3:
            raise ValidationError("Sesizarea are nevoie de un subiect.")
        if not (MIN_REZUMAT <= len(rezumat) <= MAX_REZUMAT):
            raise ValidationError("Rezumatul sesizarii nu are o lungime valida.")

        # O singura sesizare deschisa per om. Nu e o limitare de resurse, ci de
        # claritate: doua fire despre acelasi caz inseamna doi administratori
        # care raspund pe jumatate, sau niciunul.
        existenta = await self._sesizari.deschisa_recenta(user_id)
        if existenta:
            return RezultatTrimitere(id=str(existenta["id"]), creata_acum=False)

        rand = await self._sesizari.creeaza(
            {
                "id_utilizator": str(user_id),
                "subiect": subiect[:200],
                "rezumat": rezumat,
                "context": context or {},
            }
        )
        if rand is None:
            raise ValidationError("Nu am putut salva sesizarea.")

        return RezultatTrimitere(id=str(rand["id"]), creata_acum=True)

    async def coada(self, doar_deschise: bool = True) -> list[dict]:
        return await self._sesizari.coada(doar_deschise)

    async def raspunde(
        self, id_cerere: str, raspuns: str, id_administrator: str, status: str = "rezolvata"
    ) -> dict:
        raspuns = (raspuns or "").strip()
        if not raspuns:
            raise ValidationError("Raspunsul nu poate fi gol.")
        if status not in STATUSURI:
            raise ValidationError(f"Statusul '{status}' nu exista.")

        rand = await self._sesizari.raspunde(id_cerere, raspuns, id_administrator, status)
        if rand is None:
            raise ResourceNotFoundError("Sesizarea nu exista.")

        # Clientul afla ca i s-a raspuns. Esecul notificarii nu pierde raspunsul,
        # care e deja scris — dar il lasa pe om sa nu stie, asa ca ramane in jurnal.
        try:
            await self._notificari.scrie_notificare(
                rand["id_utilizator"],
                "Ai primit un raspuns de la banca",
                f"{rand.get('subiect', 'Sesizarea ta')}\n\n{raspuns}",
                "info",
            )
        except Exception:  # noqa: BLE001 — vezi comentariul de mai sus
            import logging

            logging.getLogger(__name__).exception(
                "nu am putut notifica raspunsul la sesizarea %s", id_cerere
            )

        return rand

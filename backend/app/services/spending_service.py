from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.repositories.card_repository import CardRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.agents import CashflowResponse, LunaCashflow, SoldSumar

# Cate tranzactii se citesc cel mult pentru o agregare. Agregarea se face in
# Python pentru ca supabase-py nu expune group by; daca volumul creste, locul
# corect pentru asta e o view sau un RPC in Postgres (cap. 9 din ARCHITECTURE).
LIMITA_CITIRE = 500

MAX_LUNI = 12
MAX_ZILE = 180
MAX_TRANZACTII_LISTATE = 25


def _inceput_de_luna(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _luni_in_urma(moment: datetime, luni: int) -> datetime:
    an, luna = moment.year, moment.month - luni
    while luna <= 0:
        luna += 12
        an -= 1
    return _inceput_de_luna(moment.replace(year=an, month=luna))


class SpendingService:
    """Read models pentru agenti: sume agregate, nu tabele brute."""

    def __init__(
        self,
        tranzactii: TransactionRepository,
        carduri: CardRepository,
    ) -> None:
        self._tranzactii = tranzactii
        self._carduri = carduri

    async def sold_sumar(self, user_id: UUID) -> SoldSumar:
        carduri = await self._carduri.list_owned(user_id)
        total = sum(float(card["sold_curent"]) for card in carduri if not card["is_blocked"])
        return SoldSumar(
            total_disponibil=round(total, 2),
            numar_carduri=len(carduri),
            carduri_blocate=sum(1 for card in carduri if card["is_blocked"]),
        )

    async def cashflow_lunar(
        self,
        user_id: UUID,
        luni: int = 3,
        valuta: str = "RON",
    ) -> CashflowResponse:
        luni = max(1, min(luni, MAX_LUNI))
        acum = datetime.now(timezone.utc)
        start = _luni_in_urma(acum, luni - 1)

        randuri = await self._tranzactii.list_between(user_id, start, acum, LIMITA_CITIRE)

        incasari: dict[str, float] = defaultdict(float)
        cheltuieli: dict[str, float] = defaultdict(float)
        for rand in randuri:
            if rand["valuta"] != valuta:
                continue
            cheie = str(rand["creat_la"])[:7]
            suma = float(rand["suma"])
            if str(rand["id_user_send"]) == str(user_id):
                cheltuieli[cheie] += suma
            if str(rand["id_user_recieve"]) == str(user_id):
                incasari[cheie] += suma

        etichete = sorted({*incasari, *cheltuieli})
        rezultat = [
            LunaCashflow(
                luna=eticheta,
                incasari=round(incasari[eticheta], 2),
                cheltuieli=round(cheltuieli[eticheta], 2),
                net=round(incasari[eticheta] - cheltuieli[eticheta], 2),
            )
            for eticheta in etichete
        ]
        medie = round(sum(l.cheltuieli for l in rezultat) / len(rezultat), 2) if rezultat else 0.0

        return CashflowResponse(valuta=valuta, luni=rezultat, media_lunara_cheltuieli=medie)

    async def tranzactii_recente(
        self,
        user_id: UUID,
        zile: int = 30,
        limita: int = 10,
    ) -> list[dict]:
        zile = max(1, min(zile, MAX_ZILE))
        limita = max(1, min(limita, MAX_TRANZACTII_LISTATE))
        acum = datetime.now(timezone.utc)

        randuri = await self._tranzactii.list_between(
            user_id, acum - timedelta(days=zile), acum, LIMITA_CITIRE
        )

        return [
            {
                "data": str(rand["creat_la"])[:10],
                "suma": float(rand["suma"]),
                "valuta": rand["valuta"],
                "descriere": rand["descriere"],
                "directie": (
                    "iesire" if str(rand["id_user_send"]) == str(user_id) else "intrare"
                ),
            }
            for rand in randuri[:limita]
        ]

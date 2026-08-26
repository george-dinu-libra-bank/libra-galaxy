"""Read models: sume agregate, nu tabele brute (cap. 9 din ARCHITECTURE.md).

Agregarea se face acum in Python. Cand volumul creste, locul ei corect e o view
sau un RPC in Postgres, iar semnaturile de aici raman aceleasi.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.ml.caracteristici import normalizeaza
from app.ml.neregularitati import DetectorNeregularitati, Neregularitate
from app.repositories.card_repository import CardRepository
from app.repositories.cont_repository import ContRepository
from app.repositories.tranzactie_repository import TranzactieRepository
from app.schemas.analiza import (
    CashflowResponse,
    CategorieCheltuiala,
    CheltuieliPeCategorieResponse,
    LunaCashflow,
    SoldSumar,
)
from app.tools.categorii_tranzactii import categorizeaza

MAX_LUNI = 12
MAX_ZILE = 365
# 200, nu 25: /categorii/[categorie] (dashboard) are nevoie de toate
# tranzactiile lunii curente, nu doar un rezumat scurt ca la chat-ul asistentului.
MAX_TRANZACTII_LISTATE = 200


def _inceput_de_luna(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _luni_in_urma(moment: datetime, luni: int) -> datetime:
    an, luna = moment.year, moment.month - luni
    while luna <= 0:
        luna += 12
        an -= 1
    return _inceput_de_luna(moment.replace(year=an, month=luna))


class AnalizaService:
    def __init__(
        self,
        tranzactii: TranzactieRepository,
        carduri: CardRepository,
        conturi: ContRepository | None = None,
        detector: DetectorNeregularitati | None = None,
        limita_randuri: int = 1000,
    ) -> None:
        self._tranzactii = tranzactii
        self._carduri = carduri
        self._conturi = conturi
        self._detector = detector or DetectorNeregularitati()
        self._limita = limita_randuri

    async def sold_sumar(self, user_id: UUID) -> SoldSumar:
        conturi = await self._conturi.ale_utilizatorului(user_id) if self._conturi else []
        carduri = await self._carduri.ale_utilizatorului(user_id)
        return SoldSumar(
            total_disponibil=round(sum(float(c["sold"]) for c in conturi), 2),
            numar_conturi=len(conturi),
            numar_carduri=len(carduri),
            carduri_blocate=sum(1 for c in carduri if c["is_blocked"]),
        )

    async def obtine_conturi(self, user_id: UUID) -> list[dict]:
        """Nume/IBAN complet/sold per cont, la fel ca tools/banking_tools.py:
        get_accounts — IBAN-ul e contul propriu al utilizatorului, nu un secret
        (GUARDRAILS.md #12). sold_sumar() de mai sus insumeaza fara detaliu per
        cont, deci nu poate raspunde la 'care e IBAN-ul meu'."""
        conturi = await self._conturi.ale_utilizatorului(user_id) if self._conturi else []
        return [
            {"nume": c["nume"], "iban": c["iban"], "sold": float(c["sold"])}
            for c in conturi
        ]

    async def cashflow_lunar(
        self, user_id: UUID, luni: int = 3, valuta: str = "RON"
    ) -> CashflowResponse:
        luni = max(1, min(luni, MAX_LUNI))
        acum = datetime.now(timezone.utc)
        randuri = await self._tranzactii.intre(
            user_id, _luni_in_urma(acum, luni - 1), acum, self._limita
        )

        incasari: dict[str, float] = defaultdict(float)
        cheltuieli: dict[str, float] = defaultdict(float)
        for rand in randuri:
            if rand.get("valuta") != valuta:
                continue
            luna = str(rand["creat_la"])[:7]
            suma = float(rand["suma"])
            if str(rand.get("id_user_send")) == str(user_id):
                cheltuieli[luna] += suma
            if str(rand.get("id_user_recieve")) == str(user_id):
                incasari[luna] += suma

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

    async def cheltuieli_pe_categorie_luna_curenta(
        self, user_id: UUID, valuta: str = "RON"
    ) -> CheltuieliPeCategorieResponse:
        """Cheltuielile lunii calendaristice curente, pe categorie — pentru
        widgetul de dashboard (stil George/BCR). Categoria vine din acelasi
        categorizeaza() determinist ca la tranzactii_recente(), niciodata
        ghicit de un model (CLAUDE.md #25)."""
        acum = datetime.now(timezone.utc)
        inceput = _inceput_de_luna(acum)
        randuri = await self._tranzactii.intre(user_id, inceput, acum, self._limita)

        totaluri: dict[str, float] = defaultdict(float)
        for rand in randuri:
            if rand.get("valuta") != valuta:
                continue
            if str(rand.get("id_user_send")) != str(user_id):
                continue  # doar cheltuielile (bani iesiti), nu incasarile
            categorie = categorizeaza(rand.get("descriere"), None)
            totaluri[categorie] += float(rand["suma"])

        categorii = sorted(
            (CategorieCheltuiala(categorie=c, total=round(t, 2)) for c, t in totaluri.items()),
            key=lambda c: c.total,
            reverse=True,
        )
        return CheltuieliPeCategorieResponse(luna=inceput.strftime("%Y-%m"), valuta=valuta, categorii=categorii)

    async def tranzactii_recente(
        self, user_id: UUID, zile: int = 30, limita: int = 10
    ) -> list[dict]:
        zile = max(1, min(zile, MAX_ZILE))
        limita = max(1, min(limita, MAX_TRANZACTII_LISTATE))
        acum = datetime.now(timezone.utc)
        randuri = await self._tranzactii.intre(
            user_id, acum - timedelta(days=zile), acum, self._limita
        )
        return [
            {
                "data": str(rand["creat_la"])[:10],
                "suma": float(rand["suma"]),
                "valuta": rand.get("valuta", "RON"),
                "descriere": rand.get("descriere"),
                "directie": "iesire"
                if str(rand.get("id_user_send")) == str(user_id)
                else "intrare",
                # Determinist (tools/categorii_tranzactii.py), niciodata ghicit de model.
                "categorie": categorizeaza(rand.get("descriere"), None),
            }
            for rand in randuri[:limita]
        ]

    async def neregularitati(self, user_id: UUID, zile: int = 180) -> list[Neregularitate]:
        zile = max(1, min(zile, MAX_ZILE))
        acum = datetime.now(timezone.utc)
        randuri = await self._tranzactii.intre(
            user_id, acum - timedelta(days=zile), acum, self._limita
        )
        return self._detector.evalueaza(normalizeaza(randuri, user_id))

"""Read models: sume agregate, nu tabele brute (cap. 9 din ARCHITECTURE.md).

Agregarea se face acum in Python. Cand volumul creste, locul ei corect e o view
sau un RPC in Postgres, iar semnaturile de aici raman aceleasi.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.errors import ConfigurationError, ResourceNotFoundError, ValidationError
from app.ml.caracteristici import normalizeaza
from app.ml.neregularitati import DetectorNeregularitati, Neregularitate
from app.repositories.card_repository import CardRepository
from app.repositories.categorie_manuala_repository import CategorieManualaRepository
from app.repositories.cont_repository import ContRepository
from app.repositories.tranzactie_repository import TranzactieRepository
from app.schemas.analiza import (
    CashflowResponse,
    CategorieCheltuiala,
    CheltuieliPeCategorieResponse,
    LunaCashflow,
    SoldSumar,
)
from app.tools.categorii_tranzactii import CATEGORII_VALIDE, categorizeaza

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
        categorii_manuale: CategorieManualaRepository | None = None,
    ) -> None:
        self._tranzactii = tranzactii
        self._carduri = carduri
        self._conturi = conturi
        self._detector = detector or DetectorNeregularitati()
        self._limita = limita_randuri
        self._categorii_manuale = categorii_manuale

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

    async def cheltuieli_pe_categorie_luna_curenta(self, user_id: UUID) -> CheltuieliPeCategorieResponse:
        """Cheltuielile lunii calendaristice curente, pe categorie — pentru
        widgetul de dashboard si pagina /categorii. Categoria vine din acelasi
        categorizeaza() determinist ca la tranzactii_recente(), niciodata
        ghicit de un model (CLAUDE.md #25).

        Nu se filtreaza si nu se converteste pe nicio valuta aici — se aduna
        strict pe (categorie, valuta), cate o suma pentru fiecare pereche.
        Inainte se filtra pe o singura valuta (implicit RON), asa ca o cheltuiala
        in EUR disparea complet din widget in loc sa fie convertita si adunata;
        conversia intre valute cere cursuri, iar acelea exista doar in
        Next.js/Supabase (lib/data/curs-valutar.ts), nu in acest serviciu."""
        acum = datetime.now(timezone.utc)
        inceput = _inceput_de_luna(acum)
        randuri = await self._tranzactii.intre(user_id, inceput, acum, self._limita)
        suprascrieri = await self._suprascrieri(randuri)

        totaluri: dict[tuple[str, str], float] = defaultdict(float)
        for rand in randuri:
            if str(rand.get("id_user_send")) != str(user_id):
                continue  # doar cheltuielile (bani iesiti), nu incasarile
            categorie = suprascrieri.get(str(rand["id"])) or categorizeaza(rand.get("descriere"), None)
            valuta = rand.get("valuta") or "RON"
            totaluri[(categorie, valuta)] += float(rand["suma"])

        categorii = sorted(
            (
                CategorieCheltuiala(categorie=categorie, valuta=valuta, total=round(total, 2))
                for (categorie, valuta), total in totaluri.items()
            ),
            key=lambda c: c.total,
            reverse=True,
        )
        return CheltuieliPeCategorieResponse(luna=inceput.strftime("%Y-%m"), categorii=categorii)

    async def tranzactii_recente(
        self, user_id: UUID, zile: int = 30, limita: int = 10
    ) -> list[dict]:
        zile = max(1, min(zile, MAX_ZILE))
        limita = max(1, min(limita, MAX_TRANZACTII_LISTATE))
        acum = datetime.now(timezone.utc)
        randuri = await self._tranzactii.intre(
            user_id, acum - timedelta(days=zile), acum, self._limita
        )
        randuri = randuri[:limita]
        suprascrieri = await self._suprascrieri(randuri)
        return [
            {
                "data": str(rand["creat_la"])[:10],
                "suma": float(rand["suma"]),
                "valuta": rand.get("valuta", "RON"),
                "descriere": rand.get("descriere"),
                "directie": "iesire"
                if str(rand.get("id_user_send")) == str(user_id)
                else "intrare",
                # Suprascrierea confirmata de utilizator (0043) are prioritate;
                # altfel determinist (tools/categorii_tranzactii.py), niciodata
                # ghicit de model.
                "categorie": suprascrieri.get(str(rand["id"])) or categorizeaza(rand.get("descriere"), None),
            }
            for rand in randuri
        ]

    async def _suprascrieri(self, randuri: list[dict]) -> dict[str, str]:
        if not self._categorii_manuale or not randuri:
            return {}
        return await self._categorii_manuale.pentru_tranzactii([rand["id"] for rand in randuri])

    async def seteaza_categorie_manuala(self, user_id: UUID, tranzactie_id: UUID, categorie: str) -> None:
        """Scrierea reala din spatele butonului "Confirmă" din chat — niciodata
        apelata de model, doar de ruta determinista (CLAUDE.md #9)."""
        if categorie not in CATEGORII_VALIDE:
            raise ValidationError(f"Categorie necunoscuta: {categorie}")

        # RLS (0002: "tranzactii proprii: select") face verificarea de
        # proprietate: daca tranzactia nu exista sau nu e a lui user_id (clientul
        # cu care a fost construit acest service), .obtine() intoarce None.
        tranzactie = await self._tranzactii.obtine(tranzactie_id)
        if tranzactie is None:
            raise ResourceNotFoundError("Tranzactia nu exista sau nu iti apartine.")

        if self._categorii_manuale is None:
            raise ConfigurationError("AnalizaService a fost construit fara CategorieManualaRepository.")
        await self._categorii_manuale.seteaza(tranzactie_id, user_id, categorie)

    async def neregularitati(self, user_id: UUID, zile: int = 180) -> list[Neregularitate]:
        zile = max(1, min(zile, MAX_ZILE))
        acum = datetime.now(timezone.utc)
        randuri = await self._tranzactii.intre(
            user_id, acum - timedelta(days=zile), acum, self._limita
        )
        return self._detector.evalueaza(normalizeaza(randuri, user_id))

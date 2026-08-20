"""Raportul de analiza pentru un cont semnalat.

Continutul e determinist: aceleasi tranzactii dau acelasi raport, de fiecare
data. E o cerinta, nu o preferinta — un raport pe baza caruia cineva blocheaza
un cont trebuie sa poata fi refacut identic mai tarziu, si trebuie sa contina
exact ce a produs detectorul, nu o repovestire.

Sinteza in cuvinte, daca e ceruta, vine separat (`sinteza.py`) si se aseaza
deasupra faptelor, niciodata in locul lor.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.ml.caracteristici import normalizeaza
from app.ml.neregularitati import DetectorNeregularitati, Neregularitate
from app.repositories.admin_repository import AdminRepository

MAX_ZILE = 365
MAX_UTILIZATORI = 100

ETICHETE_TIP = {
    "suma_neobisnuita": "Suma neobisnuita",
    "plata_dublata": "Plata dublata",
    "comerciant_nou": "Comerciant nou, suma mare",
    "rafala_de_plati": "Rafala de plati",
    "tipar_neobisnuit": "Tipar neobisnuit",
}


@dataclass(frozen=True, slots=True)
class RezumatCont:
    """Un rand din lista administratorului."""

    id_utilizator: str
    nume: str
    email: str
    numar_semnalari: int
    scor_maxim: float
    suma_totala: float
    tipuri: list[str]


@dataclass(slots=True)
class Raport:
    id_utilizator: str
    nume: str
    email: str
    iban: str
    zile: int
    generat_la: datetime
    constatari: list[Neregularitate]
    total_tranzactii: int
    sinteza: str | None = None
    pe_tip: dict[str, int] = field(default_factory=dict)

    @property
    def suma_semnalata(self) -> float:
        return round(sum(c.suma for c in self.constatari), 2)

    @property
    def scor_maxim(self) -> float:
        return max((c.scor for c in self.constatari), default=0.0)


class RaportService:
    def __init__(
        self,
        admin: AdminRepository,
        detector: DetectorNeregularitati | None = None,
        limita_randuri: int = 1000,
    ) -> None:
        self._admin = admin
        self._detector = detector or DetectorNeregularitati.cu_model_de_pe_disc()
        self._limita = limita_randuri

    @staticmethod
    def _interval(zile: int) -> tuple[datetime, datetime, int]:
        zile = max(1, min(zile, MAX_ZILE))
        acum = datetime.now(timezone.utc)
        return acum - timedelta(days=zile), acum, zile

    async def _constatari(self, user_id: UUID, start: datetime, sfarsit: datetime):
        randuri = await self._admin.tranzactii(user_id, start, sfarsit, self._limita)
        return randuri, self._detector.evalueaza(normalizeaza(randuri, user_id))

    async def conturi_semnalate(self, zile: int = 30) -> list[RezumatCont]:
        """Conturile cu semnalari, cel mai greu caz primul.

        Se uita la fiecare utilizator care a platit ceva in perioada. Cat timp
        vorbim de sute de conturi e in regula asa; peste, locul acestei numarari
        e o view materializata in Postgres, nu o bucla in Python.
        """
        start, sfarsit, _ = self._interval(zile)
        utilizatori = await self._admin.utilizatori_cu_plati(start, MAX_UTILIZATORI)
        if not utilizatori:
            return []

        profiluri = await self._admin.profiluri(utilizatori)

        rezumate: list[RezumatCont] = []
        for user_id in utilizatori:
            _, constatari = await self._constatari(user_id, start, sfarsit)
            if not constatari:
                continue

            profil = profiluri.get(str(user_id), {})
            rezumate.append(
                RezumatCont(
                    id_utilizator=str(user_id),
                    nume=profil.get("nume", "necunoscut"),
                    email=profil.get("email", ""),
                    numar_semnalari=len(constatari),
                    scor_maxim=max(c.scor for c in constatari),
                    suma_totala=round(sum(c.suma for c in constatari), 2),
                    tipuri=sorted({c.tip for c in constatari}),
                )
            )

        rezumate.sort(key=lambda r: r.scor_maxim, reverse=True)
        return rezumate

    async def raport(self, user_id: UUID, zile: int = 180) -> Raport | None:
        start, sfarsit, zile = self._interval(zile)

        profil = await self._admin.profil(user_id)
        if profil is None:
            return None

        randuri, constatari = await self._constatari(user_id, start, sfarsit)

        pe_tip: dict[str, int] = {}
        for c in constatari:
            pe_tip[c.tip] = pe_tip.get(c.tip, 0) + 1

        return Raport(
            id_utilizator=str(user_id),
            nume=profil.get("nume", "necunoscut"),
            email=profil.get("email", ""),
            iban=profil.get("iban_cont", ""),
            zile=zile,
            generat_la=sfarsit,
            constatari=constatari,
            total_tranzactii=len(randuri),
            pe_tip=pe_tip,
        )

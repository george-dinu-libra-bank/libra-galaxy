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



# -----------------------------------------------------------------------------
# Gravitatea unui cont
#
# Severitatea unei constatari raspunde la "cat de grava e ACEASTA plata".
# Ordonarea conturilor raspunde la altceva: "pe cine ma uit primul". Sunt
# intrebari diferite, si `max(severitate)` raspundea doar la prima.
#
# Consecinta, vazuta pe date reale: un cont cu o singura plata dublata de 1.400
# de lei aparea inaintea unuia cu 19 semnalari insumand 100 de milioane, fiindca
# dublarea confirmata are severitatea cea mai mare. Cea mai grava plata a lui era
# mai putin grava, dar contul lui era clar mai urgent.
#
# Volumul si suma nu creeaza gravitate din nimic — un cont fara constatari
# ramane in afara listei indiferent cati bani misca — dar o amplifica.
# -----------------------------------------------------------------------------

# Peste atatea semnalari, inca una nu mai schimba urgenta: e deja mult.
SATURATIE_SEMNALARI = 20
# Idem pentru bani. Scara e logaritmica: intre 1.000 si 10.000 de lei e aceeasi
# distanta ca intre 1 si 10 milioane, fiindca asa se citeste un ordin de marime.
SATURATIE_SUMA = 1_000_000.0

# Cat cantareste fiecare intrebare. Cea mai grava constatare ramane cu ponderea
# cea mai mare: ce s-a intamplat conteaza mai mult decat cat de des.
PONDERE_SEVERITATE = 0.55
PONDERE_NUMAR = 0.25
PONDERE_SUMA = 0.20


def gravitate_cont(constatari: list[Neregularitate]) -> int:
    """Cat de urgent merita contul o privire, pe aceeasi scara 1-100."""
    import math

    if not constatari:
        return 0

    cea_mai_grava = max(c.scor for c in constatari)
    suma = sum(c.suma for c in constatari)

    parte_numar = min(len(constatari) / SATURATIE_SEMNALARI, 1.0) * 100
    parte_suma = (
        min(math.log10(1 + max(suma, 0.0)) / math.log10(1 + SATURATIE_SUMA), 1.0) * 100
    )

    return max(
        1,
        min(
            100,
            round(
                PONDERE_SEVERITATE * cea_mai_grava
                + PONDERE_NUMAR * parte_numar
                + PONDERE_SUMA * parte_suma
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class RezumatCont:
    """Un rand din lista administratorului."""

    id_utilizator: str
    nume: str
    email: str
    numar_semnalari: int
    # Cea mai grava constatare de pe cont — un fapt despre o singura plata.
    scor_maxim: float
    # Cat de urgent merita contul o privire, tinand cont si de cate sunt si de
    # cati bani. Dupa asta se ordoneaza lista.
    gravitate: int
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
                    gravitate=gravitate_cont(constatari),
                    suma_totala=round(sum(c.suma for c in constatari), 2),
                    tipuri=sorted({c.tip for c in constatari}),
                )
            )

        rezumate.sort(key=lambda r: (r.gravitate, r.scor_maxim), reverse=True)
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

"""Hotararea administratorului asupra unui cont semnalat.

A consemna o constatare si a lua o masura sunt doua acte diferite, si raman
separate si aici: o analiza scrie in istoric si atat, iar blocarea sau
deblocarea se cer anume, prin `aplica_blocarea`. Un administrator poate hotari
ca un caz e suspect fara sa blocheze inca nimic — de exemplu pana verifica
cineva mai departe — si poate bloca oricand, ca act de sine statator.

Nimic nu se aplica pe contul cuiva fara ca un om sa fi cerut acea masura anume.
Detectia propune, nu dispune.

Ce NU face blocarea, si de ce e scris aici, nu doar in migrare: opreste platile
cu cardul, fiindca RPC-ul de plata verifica `carduri.is_blocked`, dar nu
opreste transferurile pe IBAN. `public.core_banking` nu se uita la starea
cardurilor, iar modificarea ei ar fi insemnat rescrierea unei functii
existente. Aplicatia verifica inainte de transfer (vezi frontend), ceea ce
acopera drumul normal — nu si pe cineva care ar chema RPC-ul direct.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from app.core.errors import ResourceNotFoundError, ValidationError
from app.repositories.admin_repository import AdminRepository, AnalizaRepository

logger = logging.getLogger(__name__)

DECIZII = ("acceptat", "frauda", "deblocat")
MAX_OBSERVATIE = 2000

# Textele care ajung la client. Scrise aici, nu in interfata: sunt mesaje
# oficiale ale bancii si trebuie sa fie aceleasi indiferent de unde pleaca.
MESAJE = {
    "frauda": (
        "blocare",
        "Cardurile tale au fost blocate temporar",
        "Am observat activitate neobisnuita pe contul tau si, ca masura de "
        "protectie, cardurile au fost blocate temporar. Transferurile nu sunt "
        "afectate. Te rugam sa contactezi banca pentru a clarifica situatia.",
    ),
    "deblocat": (
        "deblocare",
        "Cardurile tale au fost deblocate",
        "Verificarea s-a incheiat, iar cardurile tale functioneaza din nou "
        "normal. Iti multumim pentru rabdare.",
    ),
}


@dataclass(slots=True)
class RezultatAnaliza:
    decizie: str
    observatie: str | None
    carduri_atinse: int
    notificare_trimisa: bool
    creat_la: str


class AnalizaContService:
    def __init__(self, analize: AnalizaRepository, profiluri: AdminRepository) -> None:
        self._analize = analize
        self._profiluri = profiluri

    async def istoric(self, user_id: UUID) -> list[dict]:
        return await self._analize.istoric(user_id)

    async def decide(
        self,
        user_id: UUID,
        id_administrator: UUID,
        decizie: str,
        observatie: str | None,
        gravitate: int | None = None,
        numar_semnalari: int | None = None,
        zile: int | None = None,
        aplica_blocarea: bool = False,
    ) -> RezultatAnaliza:
        if decizie not in DECIZII:
            raise ValidationError(
                f"Decizia '{decizie}' nu e permisa; se accepta: {', '.join(DECIZII)}."
            )

        observatie = (observatie or "").strip() or None
        if observatie and len(observatie) > MAX_OBSERVATIE:
            raise ValidationError(
                f"Observatia depaseste {MAX_OBSERVATIE} de caractere."
            )

        if await self._profiluri.profil(user_id) is None:
            raise ResourceNotFoundError("Contul nu a fost gasit.")

        # Blocarea, inaintea scrierii in istoric: daca esueaza, nu vrem un rand
        # care sustine ca s-a blocat ceva ce n-a fost blocat.
        #
        # `aplica_blocarea` nu se deduce din decizie: a consemna o suspiciune de
        # frauda nu blocheaza pe nimeni. Cardurile se ating doar cand
        # administratorul a apasat butonul de blocare sau de deblocare.
        carduri_atinse = 0
        blocheaza = decizie == "frauda" and aplica_blocarea
        if blocheaza:
            carduri_atinse = await self._analize.schimba_blocarea(user_id, True)
        elif decizie == "deblocat":
            carduri_atinse = await self._analize.schimba_blocarea(user_id, False)

        rand = await self._analize.scrie_analiza(
            {
                "id_utilizator": str(user_id),
                "id_administrator": str(id_administrator),
                "decizie": decizie,
                "observatie": observatie,
                "gravitate": gravitate,
                "numar_semnalari": numar_semnalari,
                "zile_analizate": zile,
                "carduri_blocate": carduri_atinse,
            }
        )

        # Notificarea, ultima si tolerata la esec: un client blocat fara mesaj e
        # o problema, dar o notificare esuata nu justifica pierderea deciziei si
        # nici anularea unei blocari deja aplicate. Ramane in jurnal.
        notificare_trimisa = False
        # Clientul e anuntat cand i se schimba situatia, nu cand cineva scrie o
        # observatie despre el. O suspiciune consemnata fara masuri nu-l sperie.
        anunta = (blocheaza or decizie == "deblocat") and carduri_atinse > 0
        if anunta and decizie in MESAJE:
            tip, titlu, mesaj = MESAJE[decizie]
            if observatie:
                mesaj = f"{mesaj}\n\nObservatia analistului: {observatie}"
            try:
                await self._analize.scrie_notificare(user_id, titlu, mesaj, tip)
                notificare_trimisa = True
            except Exception:
                logger.exception(
                    "nu am putut trimite notificarea catre %s dupa decizia '%s'",
                    user_id,
                    decizie,
                )

        return RezultatAnaliza(
            decizie=decizie,
            observatie=observatie,
            carduri_atinse=carduri_atinse,
            notificare_trimisa=notificare_trimisa,
            creat_la=str(rand.get("creat_la")) if rand else "",
        )

"""Hotararea administratorului asupra unui cont semnalat.

A consemna o constatare si a lua o masura sunt doua acte diferite, si raman
separate si aici: o analiza scrie in istoric si atat, iar blocarea sau
deblocarea se cer anume, prin `aplica_blocarea`. Un administrator poate hotari
ca un caz e suspect fara sa blocheze inca nimic — de exemplu pana verifica
cineva mai departe — si poate bloca oricand, ca act de sine statator.

Nimic nu se aplica pe contul cuiva fara ca un om sa fi cerut acea masura anume.
Detectia propune, nu dispune.

Blocarea opreste tot ce pleaca din conturile omului: si platile cu cardul, si
transferurile. Bariera e un trigger pe `conturi_bancare` (0030), care refuza
orice scadere de sold pe un cont blocat — deci tine si cand cineva cheama
RPC-ul direct, ocolind aplicatia. Banii pot in continuare INTRA intr-un cont
blocat: altfel masura ar lovi si in cei care ii trimit bani.

Pana la 0030 blocarea se facea pe `carduri.is_blocked` si nu oprea
transferurile. Acela era si steagul prin care clientul isi bloca un card
pierdut, asa ca cele doua se calcau reciproc.
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
        "Contul tău a fost blocat temporar",
        "Am observat activitate neobișnuită pe contul tău și, ca măsură de "
        "protecție, retragerile și plățile au fost oprite temporar. Banii care "
        "vin către tine intră în continuare normal. Te rugăm să contactezi "
        "banca pentru a clarifica situația.",
    ),
    "deblocat": (
        "deblocare",
        "Contul tău a fost deblocat",
        "Verificarea s-a încheiat, iar contul tău funcționează din nou normal. "
        "Îți mulțumim pentru răbdare.",
    ),
}


@dataclass(slots=True)
class RezultatAnaliza:
    decizie: str
    observatie: str | None
    conturi_atinse: int
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
        conturi_atinse = 0
        blocheaza = decizie == "frauda" and aplica_blocarea
        if blocheaza:
            conturi_atinse = await self._analize.schimba_blocarea(user_id, True)
        elif decizie == "deblocat":
            conturi_atinse = await self._analize.schimba_blocarea(user_id, False)

        rand = await self._analize.scrie_analiza(
            {
                "id_utilizator": str(user_id),
                "id_administrator": str(id_administrator),
                "decizie": decizie,
                "observatie": observatie,
                "gravitate": gravitate,
                "numar_semnalari": numar_semnalari,
                "zile_analizate": zile,
                "conturi_blocate": conturi_atinse,
            }
        )

        # Notificarea, ultima si tolerata la esec: un client blocat fara mesaj e
        # o problema, dar o notificare esuata nu justifica pierderea deciziei si
        # nici anularea unei blocari deja aplicate. Ramane in jurnal.
        notificare_trimisa = False
        # Clientul e anuntat cand i se schimba situatia, nu cand cineva scrie o
        # observatie despre el. O suspiciune consemnata fara masuri nu-l sperie.
        anunta = (blocheaza or decizie == "deblocat") and conturi_atinse > 0
        if anunta and decizie in MESAJE:
            tip, titlu, mesaj = MESAJE[decizie]
            if observatie:
                mesaj = f"{mesaj}\n\nObservația analistului: {observatie}"
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
            conturi_atinse=conturi_atinse,
            notificare_trimisa=notificare_trimisa,
            creat_la=str(rand.get("creat_la")) if rand else "",
        )

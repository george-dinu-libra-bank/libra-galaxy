"""Etapa 'documente' — citeste adeverinta cu un model, in paralel cu regex-ul.

Nu inlocuieste `app/credit/adeverinta.py`: ruleaza PESTE el. Cand cele doua
difera, diferenta e ea insasi un semnal pentru etapa de coerenta — de-aia
`coerenta.py` prefera aceasta extractie cand exista, dar cade pe cifra din
`extras` (regex) cand pipeline-ul n-a putut chema modelul.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.credit.ai.contracte import SCHEMA_EXTRACTIE_DOCUMENT, ExtractieDocument
from app.credit.ai.prompturi import SISTEM_DOCUMENTE, mesaj_utilizator_documente
from app.providers.base import ChatMessage, StructuredChatProvider


@dataclass(frozen=True, slots=True)
class RezultatDocumente:
    extractie: ExtractieDocument
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    deployment: str


def _decimal(date: dict, cheie: str) -> Decimal | None:
    valoare = date.get(cheie)
    if valoare is None:
        return None
    try:
        return Decimal(str(valoare))
    except InvalidOperation:
        return None


async def ruleaza(provider: StructuredChatProvider, text_document: str) -> RezultatDocumente:
    """`text_document` e ce s-a salvat deja la incarcare (`extras.text`, taiat
    la 4000 caractere) — nu se reciteste fisierul din storage."""
    mesaje = [
        ChatMessage(role="system", content=SISTEM_DOCUMENTE),
        ChatMessage(role="user", content=mesaj_utilizator_documente(text_document)),
    ]
    completare = await provider.complete_json(mesaje, "extractie_adeverinta", SCHEMA_EXTRACTIE_DOCUMENT)
    date = completare.data

    extractie = ExtractieDocument(
        venit_net=_decimal(date, "venit_net"),
        venit_brut=_decimal(date, "venit_brut"),
        angajator=date.get("angajator") or None,
        cui_angajator=date.get("cui_angajator") or None,
        perioada=date.get("perioada") or None,
        functie=date.get("functie") or None,
        are_stampila=date.get("are_stampila"),
        are_semnatura=date.get("are_semnatura"),
        incredere=float(date.get("incredere") or 0),
        citate={cheie: text for cheie, text in (date.get("citate") or {}).items() if text},
    )
    return RezultatDocumente(
        extractie=extractie,
        tokens_in=completare.tokens_in,
        tokens_out=completare.tokens_out,
        tokens_cached=completare.tokens_cached,
        deployment=completare.deployment,
    )

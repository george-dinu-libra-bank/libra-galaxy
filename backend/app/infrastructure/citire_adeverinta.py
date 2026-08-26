"""Citirea unei adeverinte de venit incarcate — de la octeti la cifre.

Compune bucatile: furnizorul de OCR (retea), parserul pur din `credit/adeverinta.py`
si rezervele locale. `credit/` ramane fara retea si fara IO, deci testabil singur;
aici sta singura parte care stie ca exista un furnizor.

**Ordinea: Azure intai, mereu.**

Nu se mai incearca stratul de text al PDF-ului inainte. Ar fi gratis si exact pe
caractere, dar caracterele nu sunt problema — structura e. Pe o adeverinta in
tabel, textul plat da randul

    Media Neta   15.000,00   8.774,50   0,00

din care nu se poate sti care coloana e a netului; parserul ia primul numar de
dupa eticheta, adica **brutul**. Un venit gresit e mai rau decat unul lipsa: pe
el se acorda un credit. Layout intoarce celulele cu indici de rand si coloana,
deci coloana „Venit Net" se citeste, nu se ghiceste — si asta merita cei ~10
bani pe document.

Doua incercari, in ordinea increderii, si amandoua din acelasi apel:

1. **Tabelele** (`venit_din_tabele`) — cand adeverinta e un tabel, coloana
   spune singura ce e. Nimic de interpretat.
2. **Randurile** (`citeste_adeverinta`) — cand adeverinta e text curgator
   („Salariul net lunar: 4.850,00 lei"), care n-are tabel de citit.

Rezerva, doar cand Azure nu raspunde sau nu e configurat: stratul de text al
PDF-ului, apoi Tesseract. Amandoua dau text plat, deci pe o adeverinta in tabel
raman expuse la aceeasi capcana — de-aia sunt rezerva, nu drum principal.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.errors import AiProviderError, AiProviderUnavailableError
from app.credit.adeverinta import (
    DateAdeverinta,
    angajator_din_tabele,
    citeste_adeverinta,
    vechime_din_tabele,
    venit_din_tabele,
)
from app.infrastructure.document_text import text_din_document
from app.providers.document_intelligence import AzureDocumentIntelligence, TextCitit

logger = logging.getLogger(__name__)

# Increderea data unei citiri din tabel. Mai mare decat orice scor din parsarea
# de text (maximul acolo e 0.9, pentru o suma lipita de eticheta): acolo se
# masoara cat de aproape statea numarul de un cuvant-cheie, aici coloana chiar
# scrie ce e. Nu 1.0 — antetul tot a fost citit de o masina.
INCREDERE_TABEL = 0.95


async def _prin_azure(continut: bytes, content_type: str) -> TextCitit | None:
    settings = get_settings()
    if not settings.document_intelligence_configured:
        return None

    try:
        return await AzureDocumentIntelligence(settings).citeste(continut, content_type)
    except (AiProviderError, AiProviderUnavailableError):
        logger.warning("citire_adeverinta: Azure a esuat, trec pe rezerva", exc_info=True)
        return None


async def citeste(continut: bytes, content_type: str | None) -> DateAdeverinta:
    """Ce s-a putut citi dintr-o adeverinta incarcata."""
    tip = content_type or "application/octet-stream"

    citit = await _prin_azure(continut, tip)
    if citit is None:
        return citeste_adeverinta(await text_din_document(continut, content_type))

    # Citirea din text ramane baza: acopera adeverintele scrise curgator si
    # aduce campurile pe care tabelele nu le au. Peste ea se pune ce s-a putut
    # citi din celule, care e mereu mai sigur decat o potrivire de vecinatate.
    date = citeste_adeverinta(citit.text)

    venit = venit_din_tabele(citit.tabele)
    angajator = angajator_din_tabele(citit.tabele) or date.angajator
    vechime = vechime_din_tabele(citit.tabele) or date.vechime_luni

    if venit is None:
        return DateAdeverinta(
            venit_net=date.venit_net,
            angajator=angajator,
            vechime_luni=vechime,
            incredere=date.incredere,
            text_brut=citit.text,
        )

    return DateAdeverinta(
        venit_net=venit,
        angajator=angajator,
        vechime_luni=vechime,
        incredere=INCREDERE_TABEL,
        text_brut=citit.text,
        sursa="tabel",
    )

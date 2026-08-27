"""Text dintr-un fisier incarcat, indiferent daca e poza sau PDF — fara retea.

Granita dintre „un fisier a ajuns pe server" si „avem text de interpretat".
Ce se face cu textul e treaba lui `app/credit/adeverinta.py`, care e pur si
testabil; aici sunt partile murdare — Tesseract si structura unui PDF.

**Acesta e drumul de rezerva.** Citirea adeverintelor merge prin Azure Document
Intelligence (`infrastructure/citire_adeverinta.py`), care intoarce si structura
de tabel, nu doar caracterele. Aici se ajunge doar cand Azure nu e configurat sau
nu raspunde. Amandoua drumurile de mai jos dau text plat, deci pe o adeverinta in
tabel raman expuse la confuzia brut/net — motiv suficient sa nu fie principale.

Doua incercari, in ordinea increderii:

1. **PDF cu strat de text** — `pypdf` citeste exact ce a scris programul care a
   generat documentul. Zero interpretare, zero erori de citire.
2. **Poza sau PDF scanat** — Tesseract, in container. Pentru PDF se scot intai
   imaginile incorporate: Tesseract nu stie ce e un PDF.

Cand niciunul nu da nimic, se intoarce sirul gol. Serviciul marcheaza documentul
`ilizibil` si analistul scrie cifra de mana — un rezultat prost, dar declarat.
"""

from __future__ import annotations

import io
import logging

from anyio import to_thread
from pypdf import PdfReader

# Aceeasi extragere ca la atasamentele din asistent; nu se scrie a doua oara.
from app.attachments.extraction import extract_pdf_text
from app.infrastructure.ocr import extrage_text

logger = logging.getLogger(__name__)

TIP_PDF = "application/pdf"

# Cate pagini se scaneaza dintr-un PDF fara strat de text. O adeverinta are una,
# rar doua; restul ar fi altceva, iar OCR-ul e scump in timp de CPU.
PAGINI_SCANATE = 3


def _imagini_din_pdf(continut: bytes) -> list[bytes]:
    """Imaginile incorporate din primele pagini, pentru PDF-urile scanate."""
    try:
        reader = PdfReader(io.BytesIO(continut))
    except Exception:
        logger.warning("document_text: PDF ilizibil")
        return []

    imagini: list[bytes] = []
    for pagina in reader.pages[:PAGINI_SCANATE]:
        try:
            imagini.extend(imagine.data for imagine in pagina.images)
        except Exception:
            # O pagina cu un filtru de imagine pe care pypdf nu-l stie nu
            # trebuie sa opreasca citirea celorlalte.
            logger.exception("document_text: nu am putut extrage imaginile dintr-o pagina")

    return imagini


async def _prin_tesseract(continut: bytes, content_type: str) -> str:
    """Pe un thread: sunt secunde de CPU care ar bloca tot backendul."""
    if (content_type or "").lower().startswith(TIP_PDF):
        imagini = await to_thread.run_sync(_imagini_din_pdf, continut)
        bucati = [await to_thread.run_sync(extrage_text, imagine) for imagine in imagini]
        return "\n".join(bucata for bucata in bucati if bucata.strip())

    return await to_thread.run_sync(extrage_text, continut)


async def text_din_document(continut: bytes, content_type: str | None) -> str:
    """Textul citibil dintr-un fisier incarcat. Sirul gol inseamna „n-am putut"."""
    if (content_type or "").lower().startswith(TIP_PDF):
        try:
            text = await to_thread.run_sync(extract_pdf_text, continut)
        except Exception:
            logger.exception("document_text: extragerea stratului de text a esuat")
            text = ""

        if text.strip():
            return text

    return await _prin_tesseract(continut, content_type or "")

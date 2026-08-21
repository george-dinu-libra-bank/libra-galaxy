"""Text dintr-un fisier incarcat, indiferent daca e poza sau PDF.

Granita dintre „un fisier a ajuns pe server" si „avem text de interpretat".
Ce se face cu textul e treaba lui `app/credit/adeverinta.py`, care e pur si
testabil; aici sunt partile murdare — Tesseract si structura unui PDF.

Trei drumuri, in ordinea increderii:

1. **PDF cu strat de text** — `pypdf` citeste exact ce a scris programul care a
   generat documentul. Zero interpretare, zero erori de citire. Adeverintele
   emise electronic, care sunt majoritatea, cad aici.
2. **PDF scanat** — n-are strat de text, dar are scanul ca imagine incorporata.
   `pypdf` o extrage si merge la Tesseract. Fara `poppler` sau `pdf2image`,
   care n-ar mai incapea in imaginea de Docker pentru un caz de margine.
3. **Poza** — direct la Tesseract.

Cand niciunul nu da nimic, se intoarce sirul gol. Serviciul marcheaza documentul
`ilizibil` si analistul scrie cifra de mana — un rezultat prost, dar declarat.
"""

from __future__ import annotations

import io
import logging

from pypdf import PdfReader

# Aceeasi extragere ca la atasamentele din asistent; nu se scrie a doua oara.
from app.attachments.extraction import extract_pdf_text
from app.infrastructure.ocr import extrage_text

logger = logging.getLogger(__name__)

TIP_PDF = "application/pdf"

# Cate pagini se scaneaza dintr-un PDF fara strat de text. O adeverinta are una,
# rar doua; restul ar fi altceva, iar OCR-ul e scump.
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


def text_din_document(continut: bytes, content_type: str | None) -> str:
    """Textul citibil dintr-un fisier incarcat. Sirul gol inseamna „n-am putut"."""
    if (content_type or "").lower().startswith(TIP_PDF):
        try:
            text = extract_pdf_text(continut)
        except Exception:
            logger.exception("document_text: extragerea stratului de text a esuat")
            text = ""

        if text.strip():
            return text

        # Fara strat de text: e un scan. Se incearca imaginile din el.
        return "\n".join(
            bucata for bucata in (extrage_text(imagine) for imagine in _imagini_din_pdf(continut))
            if bucata.strip()
        )

    return extrage_text(continut)

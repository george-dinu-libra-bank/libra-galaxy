"""Extragere de text din PDF — determinista, nu OCR/vision (CLAUDE.md #16)."""

from __future__ import annotations

import base64
import io

from pypdf import PdfReader

MAX_PDF_PAGES = 30


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    pages = reader.pages[:MAX_PDF_PAGES]
    texts = [page.extract_text() or "" for page in pages]
    return "\n\n".join(text.strip() for text in texts if text.strip())


def to_data_uri(content: bytes, content_type: str) -> str:
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"

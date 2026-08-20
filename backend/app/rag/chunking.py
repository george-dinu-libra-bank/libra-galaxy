"""Strategii de chunking (docs/AI_ARCHITECTURE.md #7) — nu o singura fereastra pentru orice document.

chunk_id e adresat prin continut: orice schimbare de text sau pozitie schimba
id-ul, ceea ce sta la baza reindexarii incrementale din indexing.py.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    section: str | None
    text: str
    position: int


def chunk_id_for(document_id: str, version: int, position: int, text: str) -> str:
    payload = f"{document_id}\0{version}\0{position}\0{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def section_aware_chunk(document_id: str, version: int, content: str) -> list[Chunk]:
    """O sectiune (## / ###) e o unitate de sens si o unitate citabila — potrivita
    pentru politici, proceduri, produse si FAQ, care au structura de titluri."""
    headings = list(_HEADING_RE.finditer(content))

    if not headings:
        text = content.strip()
        if not text:
            return []
        return [Chunk(chunk_id=chunk_id_for(document_id, version, 0, text), section=None, text=text, position=0)]

    chunks: list[Chunk] = []
    position = 0

    first_start = headings[0].start()
    preamble = content[:first_start].strip()
    if preamble:
        chunks.append(
            Chunk(chunk_id=chunk_id_for(document_id, version, position, preamble), section=None, text=preamble, position=position)
        )
        position += 1

    for index, match in enumerate(headings):
        section_title = match.group(2).strip()
        start = match.start()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        section_text = content[start:end].strip()

        if not section_text:
            continue

        chunks.append(
            Chunk(
                chunk_id=chunk_id_for(document_id, version, position, section_text),
                section=section_title,
                text=section_text,
                position=position,
            )
        )
        position += 1

    return chunks


def fixed_window_chunk(
    document_id: str, version: int, content: str, *, window_words: int = 150, overlap_words: int = 25
) -> list[Chunk]:
    """Fereastra glisanta pe cuvinte — pentru documente fara structura de titluri de incredere
    (educatie financiara, documente incarcate de utilizator, extrase de cont)."""
    words = content.split()
    if not words:
        return []

    step = max(window_words - overlap_words, 1)
    chunks: list[Chunk] = []
    position = 0

    for start in range(0, len(words), step):
        segment = " ".join(words[start : start + window_words])
        if not segment.strip():
            continue
        chunks.append(
            Chunk(chunk_id=chunk_id_for(document_id, version, position, segment), section=None, text=segment, position=position)
        )
        position += 1
        if start + window_words >= len(words):
            break

    return chunks

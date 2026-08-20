"""Extractie determinista de memorie inter-sesiuni (docs/AI_ARCHITECTURE.md #6).

Aceeasi ratiune ca la orchestration/intent.py: o tabela de fraze e gratuita,
instanta, reproductibila si testabila unitar — un apel de model suplimentar
per tura ar costa latenta si bani, exact opusul cererii ca aplicatia sa
ruleze mai repede, si ar introduce un pas nedeterminist greu de testat.

Filtrul dur din `_pare_stare_bancara` e mecanismul, nu doar conventia, prin
care se respecta CLAUDE.md §24/§25: memoria conversationala nu poate deveni
niciodata stare bancara, chiar daca fraza utilizatorului pare o preferinta
("prefer sa pastrez 500 RON in cont" nu se salveaza niciodata).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MAX_CONTENT_CHARS = 300


def _normalize(text: str) -> str:
    """casefold + NFKD, apoi elimina semnele combinatorii — acopera si ș/ț
    cu virgula, si varianta veche cu sedila, fara tabel manual."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


# Cifre consecutive (sume, coduri), coduri de valuta, sau o forma de IBAN —
# oricare dintre ele face continutul respins, indiferent ce fraza s-a potrivit.
_CIFRE = re.compile(r"\d{2,}")
_VALUTA = re.compile(r"\b(ron|lei|eur|usd|euro|dolari)\b")
_IBAN = re.compile(r"\b[a-z]{2}\d{2}[a-z0-9]{10,30}\b")


def _pare_stare_bancara(text_normalizat: str) -> bool:
    return bool(_CIFRE.search(text_normalizat) or _VALUTA.search(text_normalizat) or _IBAN.search(text_normalizat))


# Ordine: cele mai specifice intentii primele (la fel ca in intent.py).
_MEMORY_PHRASES: list[tuple[str, tuple[str, ...]]] = [
    (
        "preferinta",
        (
            "prefer sa", "prefer ca", "vreau sa imi arati intotdeauna", "vreau mereu",
            "numeste-ma", "spune-mi", "adreseaza-te mie cu",
            "i prefer", "please call me", "always show me", "always address me as",
        ),
    ),
    (
        "intentie_declarata",
        (
            "aminteste-ti ca", "tine minte ca", "sa nu uiti ca",
            "remember that", "keep in mind that", "don't forget that",
        ),
    ),
]


@dataclass(frozen=True)
class ExtractedMemory:
    memory_type: str
    content: str


def extract_memory(user_text: str) -> ExtractedMemory | None:
    normalized = _normalize(user_text)

    if _pare_stare_bancara(normalized):
        return None

    for memory_type, phrases in _MEMORY_PHRASES:
        if any(phrase in normalized for phrase in phrases):
            content = " ".join(user_text.split())
            return ExtractedMemory(memory_type=memory_type, content=content[:MAX_CONTENT_CHARS])

    return None

"""Numarare de tokeni cu fallback si estimare de cost (docs/AI_ARCHITECTURE.md #10)."""

from __future__ import annotations

try:
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:  # tiktoken e optional — fallback-ul tine cost tracking-ul functional oricum
    _ENCODING = None


def count_tokens(text: str) -> int:
    if _ENCODING is not None:
        return len(_ENCODING.encode(text))
    return max(1, len(text) // 4)


def estimate_chat_cost(tokens_in: int, tokens_out: int, price_per_million_in: float, price_per_million_out: float) -> float:
    cost = (tokens_in / 1_000_000) * price_per_million_in + (tokens_out / 1_000_000) * price_per_million_out
    return round(cost, 6)

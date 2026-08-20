"""Compat: re-exporta app.core.config, ca modulele care inca importa de aici
(agents/{orchestrator,baza,financiar,registru}.py, llm.py, api/routes/{agents,alerte,profiles}.py)
sa nu ceara editat un import in fiecare fisier. O singura sursa reala de
adevar pentru Settings e app/core/config.py — nu adauga campuri aici."""

from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]

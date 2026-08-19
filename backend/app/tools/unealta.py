"""Ce este un tool, independent de furnizorul de model.

Schema se scrie explicit, nu se deduce din semnatura. E mai mult de scris, dar
schema e contractul pe care il vede modelul: merita sa fie vizibila in cod.
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(frozen=True, slots=True)
class Unealta:
    nume: str
    descriere: str
    executa: Callable[..., Awaitable[Any]]
    proprietati: dict = field(default_factory=dict)
    obligatorii: list[str] = field(default_factory=list)

    def definitie(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.nume,
                "description": self.descriere,
                "parameters": {
                    "type": "object",
                    "properties": self.proprietati,
                    "required": self.obligatorii,
                    "additionalProperties": False,
                },
            },
        }

"""Tool-urile agentului Financial Advisor.

`user_id` nu e parametru nicaieri: fiecare tool e o inchidere peste contextul
autentificat (cap. 7 din ARCHITECTURE.md). Modelul nu poate cere datele altui
utilizator nici daca i se sugereaza asta in mesaj.
"""

from uuid import UUID

from app.services.analiza_service import AnalizaService
from app.tools.unealta import Unealta


def construieste(service: AnalizaService, user_id: UUID) -> list[Unealta]:
    async def obtine_sold() -> dict:
        return (await service.sold_sumar(user_id)).model_dump()

    async def obtine_conturi() -> list[dict]:
        return await service.obtine_conturi(user_id)

    async def obtine_cashflow_lunar(luni: int = 3, valuta: str = "RON") -> dict:
        return (await service.cashflow_lunar(user_id, luni, valuta)).model_dump()

    async def obtine_tranzactii_recente(zile: int = 30, limita: int = 10) -> list[dict]:
        return await service.tranzactii_recente(user_id, zile, limita)

    async def obtine_neregularitati(zile: int = 180) -> list[dict]:
        return [
            {
                "data": c.data,
                "suma": c.suma,
                "valuta": c.valuta,
                "comerciant": c.comerciant,
                "tip": c.tip,
                "explicatie": c.explicatie,
            }
            for c in await service.neregularitati(user_id, zile)
        ]

    return [
        Unealta(
            nume="obtine_sold",
            descriere=(
                "Soldul disponibil, insumat pe conturile bancare ale utilizatorului. "
                "Intoarce si cate carduri are si cate sunt blocate. Pentru intrebari de "
                "tipul 'cati bani am' sau 'ce sold am'."
            ),
            executa=obtine_sold,
        ),
        Unealta(
            nume="obtine_conturi",
            descriere=(
                "Lista conturilor bancare ale utilizatorului: nume, IBAN complet si sold, pentru "
                "fiecare valuta in care are cont. Pentru intrebari de tipul 'care e IBAN-ul meu' "
                "sau 'ce conturi am' — daca are mai multe, le enumeri pe toate, cu IBAN complet."
            ),
            executa=obtine_conturi,
        ),
        Unealta(
            nume="obtine_cashflow_lunar",
            descriere=(
                "Incasarile, cheltuielile si netul pe fiecare luna calendaristica. "
                "Pentru totaluri se foloseste asta, nu lista de tranzactii."
            ),
            executa=obtine_cashflow_lunar,
            proprietati={
                "luni": {
                    "type": "integer",
                    "description": "Cate luni in urma, inclusiv luna curenta. Intre 1 si 12.",
                    "minimum": 1,
                    "maximum": 12,
                },
                "valuta": {
                    "type": "string",
                    "description": "Cod de valuta din trei litere. Implicit RON.",
                },
            },
        ),
        Unealta(
            nume="obtine_tranzactii_recente",
            descriere=(
                "Tranzactii individuale, cu data, suma, descriere, directie si o categorie "
                "determinista (restaurant, cumparaturi, utilitati, transfer, masina, locuinta, "
                "salariu etc.). Doar cand raspunsul chiar cere plati una cate una."
            ),
            executa=obtine_tranzactii_recente,
            proprietati={
                "zile": {
                    "type": "integer",
                    "description": "Cat de departe in trecut. Intre 1 si 365.",
                    "minimum": 1,
                    "maximum": 365,
                },
                "limita": {
                    "type": "integer",
                    "description": "Cate tranzactii se intorc. Intre 1 si 25.",
                    "minimum": 1,
                    "maximum": 25,
                },
            },
        ),
        Unealta(
            nume="obtine_neregularitati",
            descriere=(
                "Platile care ies din tiparul obisnuit al utilizatorului, cu tipul problemei "
                "si o explicatie in cuvinte simple. Sunt constatari statistice, nu fraude "
                "confirmate."
            ),
            executa=obtine_neregularitati,
            proprietati={
                "zile": {
                    "type": "integer",
                    "description": "Perioada analizata. Intre 1 si 365.",
                    "minimum": 1,
                    "maximum": 365,
                }
            },
        ),
    ]

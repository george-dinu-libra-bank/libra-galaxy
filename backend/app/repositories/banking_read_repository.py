from __future__ import annotations

from dataclasses import dataclass

from supabase import Client


@dataclass(frozen=True)
class AccountRow:
    id: str
    name: str
    iban: str
    balance: float
    currency: str
    created_at: str
    # Oprit de banca: din el nu mai pot pleca bani. Asistentul trebuie sa stie,
    # altfel raspunde ca totul e in regula unui om caruia tocmai i s-a blocat
    # contul (vezi tools/banking_tools.py). Implicit fals: un cont e liber pana
    # se spune altfel, iar apelantii mai vechi nu trebuie sa se schimbe.
    blocked: bool = False


@dataclass(frozen=True)
class TransactionRow:
    id: str
    amount: float
    currency: str
    description: str | None
    created_at: str
    incoming: bool
    counterparty_name: str | None


class BankingReadRepository:
    """Citire read-only pentru tool-urile agentilor, peste tabelele bancare existente.

    Nu scrie niciodata — mutatiile raman in transfer-form.tsx / actions existente
    (docs/AI_ARCHITECTURE.md: agentii nu muta bani).
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    def list_accounts(self, user_id: str) -> list[AccountRow]:
        result = (
            self._client.table("conturi_bancare")
            .select("id, nume, iban, sold, valuta, blocat_administrativ, creat_la")
            .eq("id_user", user_id)
            .order("creat_la")
            .execute()
        )
        return [
            AccountRow(
                id=row["id"], name=row["nume"], iban=row["iban"],
                # Implicit RON, la fel ca frontend/src/lib/data/conturi.ts:
                # conturile mai vechi de 0013_schimb_valutar.sql pot avea valuta null.
                balance=float(row["sold"]), currency=row.get("valuta") or "RON",
                blocked=bool(row.get("blocat_administrativ")),
                created_at=row["creat_la"],
            )
            for row in (result.data or [])
        ]

    def list_recent_transactions(self, user_id: str, limit: int = 50) -> list[TransactionRow]:
        # Inner join (embed) pe profiles, prin cele doua chei straine ale
        # tranzactiei — numele contrapartii, nu doar id-ul ei. Backend-ul
        # foloseste service_role, deci RLS pe profiles (care ar restrictiona
        # la randul propriu) nu se aplica aici.
        result = (
            self._client.table("tranzactii")
            .select(
                "id, suma, valuta, descriere, creat_la, id_user_send, id_user_recieve,"
                "expeditor:profiles!id_user_send(nume), destinatar:profiles!id_user_recieve(nume)"
            )
            .or_(f"id_user_send.eq.{user_id},id_user_recieve.eq.{user_id}")
            .order("creat_la", desc=True)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
        transactions = []
        for row in rows:
            incoming = row.get("id_user_recieve") == user_id
            counterparty = row.get("expeditor") if incoming else row.get("destinatar")
            transactions.append(
                TransactionRow(
                    id=row["id"],
                    amount=float(row["suma"]),
                    currency=row["valuta"],
                    description=row.get("descriere"),
                    created_at=row["creat_la"],
                    incoming=incoming,
                    counterparty_name=(counterparty or {}).get("nume") if counterparty else None,
                )
            )
        return transactions

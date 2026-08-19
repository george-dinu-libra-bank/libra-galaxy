from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.services.spending_service import SpendingService

EU = uuid4()
ALTCINEVA = uuid4()
ACUM = datetime.now(timezone.utc)


class TranzactiiFalse:
    def __init__(self, randuri: list[dict]) -> None:
        self.randuri = randuri

    async def list_between(self, user_id, start, end, limit=500):
        return [r for r in self.randuri if start <= _data(r) <= end]


class CarduriFalse:
    def __init__(self, randuri: list[dict]) -> None:
        self.randuri = randuri

    async def list_owned(self, user_id):
        return self.randuri


def _data(rand: dict) -> datetime:
    return datetime.fromisoformat(rand["creat_la"])


def _tranzactie(zile_in_urma: int, suma: float, iesire: bool, valuta: str = "RON") -> dict:
    moment = ACUM - timedelta(days=zile_in_urma)
    return {
        "id": str(uuid4()),
        "suma": suma,
        "valuta": valuta,
        "descriere": "test",
        "creat_la": moment.isoformat(),
        "id_user_send": str(EU) if iesire else str(ALTCINEVA),
        "id_user_recieve": str(ALTCINEVA) if iesire else str(EU),
    }


@pytest.mark.anyio
async def test_soldul_ignora_cardurile_blocate() -> None:
    service = SpendingService(
        TranzactiiFalse([]),
        CarduriFalse(
            [
                {"sold_curent": "100.50", "is_blocked": False},
                {"sold_curent": "200.00", "is_blocked": False},
                {"sold_curent": "999.99", "is_blocked": True},
            ]
        ),
    )

    sumar = await service.sold_sumar(EU)

    assert sumar.total_disponibil == 300.50
    assert sumar.numar_carduri == 3
    assert sumar.carduri_blocate == 1


@pytest.mark.anyio
async def test_cashflow_separa_intrarile_de_iesiri() -> None:
    service = SpendingService(
        TranzactiiFalse(
            [
                _tranzactie(1, 100.0, iesire=True),
                _tranzactie(2, 50.0, iesire=True),
                _tranzactie(3, 400.0, iesire=False),
                # Alta valuta: nu intra in totalul RON.
                _tranzactie(4, 1000.0, iesire=True, valuta="EUR"),
            ]
        ),
        CarduriFalse([]),
    )

    cashflow = await service.cashflow_lunar(EU, luni=1)

    assert len(cashflow.luni) == 1
    luna = cashflow.luni[0]
    assert luna.cheltuieli == 150.0
    assert luna.incasari == 400.0
    assert luna.net == 250.0


@pytest.mark.anyio
async def test_tranzactiile_recente_au_directie_si_respecta_limita() -> None:
    service = SpendingService(
        TranzactiiFalse([_tranzactie(i, 10.0 * i, iesire=i % 2 == 0) for i in range(1, 6)]),
        CarduriFalse([]),
    )

    recente = await service.tranzactii_recente(EU, zile=30, limita=3)

    assert len(recente) == 3
    assert {r["directie"] for r in recente} <= {"intrare", "iesire"}


@pytest.mark.anyio
async def test_perioada_ceruta_este_plafonata() -> None:
    service = SpendingService(TranzactiiFalse([]), CarduriFalse([]))

    cashflow = await service.cashflow_lunar(EU, luni=999)

    assert len(cashflow.luni) <= 12

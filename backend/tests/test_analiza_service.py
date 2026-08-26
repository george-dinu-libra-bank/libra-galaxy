from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.services.analiza_service import MAX_TRANZACTII_LISTATE, AnalizaService

EU = uuid4()
ALTUL = uuid4()
ACUM = datetime.now(timezone.utc)


class TranzactiiFalse:
    def __init__(self, randuri: list[dict]) -> None:
        self.randuri = randuri

    async def intre(self, user_id, start, sfarsit, limita=1000):
        return [
            r
            for r in self.randuri
            if start <= datetime.fromisoformat(r["creat_la"]) <= sfarsit
        ]


class CarduriFalse:
    def __init__(self, randuri: list[dict]) -> None:
        self.randuri = randuri

    async def ale_utilizatorului(self, user_id):
        return self.randuri


class ConturiFalse(CarduriFalse):
    pass


def _tranzactie(zile: int, suma: float, iesire: bool, valuta: str = "RON", descriere: str = "test") -> dict:
    return {
        "id": str(uuid4()),
        "suma": suma,
        "valuta": valuta,
        "descriere": descriere,
        "creat_la": (ACUM - timedelta(days=zile)).isoformat(),
        "id_user_send": str(EU) if iesire else str(ALTUL),
        "id_user_recieve": str(ALTUL) if iesire else str(EU),
    }


@pytest.mark.anyio
async def test_soldul_vine_de_pe_conturi_nu_de_pe_carduri() -> None:
    # Soldul sta pe cont; cardul e doar instrument de plata (lib/actions/transfer.ts).
    service = AnalizaService(
        TranzactiiFalse([]),
        CarduriFalse([{"sold_curent": "999.99", "is_blocked": True}]),
        ConturiFalse([{"sold": "1500.25"}, {"sold": "300.00"}]),
    )

    sumar = await service.sold_sumar(EU)

    assert sumar.total_disponibil == 1800.25
    assert sumar.numar_conturi == 2
    assert sumar.numar_carduri == 1
    assert sumar.carduri_blocate == 1


@pytest.mark.anyio
async def test_fara_conturi_soldul_e_zero_nu_o_eroare() -> None:
    service = AnalizaService(TranzactiiFalse([]), CarduriFalse([]), ConturiFalse([]))

    assert (await service.sold_sumar(EU)).total_disponibil == 0.0


@pytest.mark.anyio
async def test_obtine_conturi_intoarce_iban_ul_complet() -> None:
    # Decizie explicita (GUARDRAILS.md #12): IBAN-ul propriu nu e un secret.
    service = AnalizaService(
        TranzactiiFalse([]),
        CarduriFalse([]),
        ConturiFalse([{"nume": "Cont Curent", "iban": "RO49AAAA1B31007593840000", "sold": "1500.25"}]),
    )

    conturi = await service.obtine_conturi(EU)

    assert conturi == [{"nume": "Cont Curent", "iban": "RO49AAAA1B31007593840000", "sold": 1500.25}]


@pytest.mark.anyio
async def test_obtine_conturi_fara_conturi_intoarce_lista_goala() -> None:
    service = AnalizaService(TranzactiiFalse([]), CarduriFalse([]), ConturiFalse([]))

    assert await service.obtine_conturi(EU) == []


@pytest.mark.anyio
async def test_cashflow_separa_intrarile_de_iesiri_si_valutele() -> None:
    service = AnalizaService(
        TranzactiiFalse(
            [
                _tranzactie(1, 100.0, iesire=True),
                _tranzactie(2, 50.0, iesire=True),
                _tranzactie(3, 400.0, iesire=False),
                _tranzactie(4, 1000.0, iesire=True, valuta="EUR"),
            ]
        ),
        CarduriFalse([]),
    )

    cashflow = await service.cashflow_lunar(EU, luni=1)
    luna = cashflow.luni[0]

    assert (luna.cheltuieli, luna.incasari, luna.net) == (150.0, 400.0, 250.0)


@pytest.mark.anyio
async def test_cheltuieli_pe_categorie_agrega_si_sorteaza_descrescator() -> None:
    service = AnalizaService(
        TranzactiiFalse(
            [
                _tranzactie(0, 30.0, iesire=True, descriere="Restaurant Bistro"),
                _tranzactie(0, 20.0, iesire=True, descriere="Cafenea Starbucks"),
                _tranzactie(0, 100.0, iesire=True, descriere="Kaufland cumparaturi"),
            ]
        ),
        CarduriFalse([]),
    )

    raspuns = await service.cheltuieli_pe_categorie_luna_curenta(EU)

    assert raspuns.categorii[0].categorie == "cumparaturi"
    assert raspuns.categorii[0].total == 100.0
    assert raspuns.categorii[1].categorie == "restaurant"
    assert raspuns.categorii[1].total == 50.0  # 30 + 20, aceeasi categorie


@pytest.mark.anyio
async def test_cheltuieli_pe_categorie_exclude_incasarile() -> None:
    service = AnalizaService(
        TranzactiiFalse([_tranzactie(0, 500.0, iesire=False, descriere="Salariu")]),
        CarduriFalse([]),
    )

    raspuns = await service.cheltuieli_pe_categorie_luna_curenta(EU)

    assert raspuns.categorii == []


@pytest.mark.anyio
async def test_cheltuieli_pe_categorie_exclude_alta_valuta() -> None:
    service = AnalizaService(
        TranzactiiFalse([_tranzactie(0, 100.0, iesire=True, valuta="EUR", descriere="Restaurant Paris")]),
        CarduriFalse([]),
    )

    raspuns = await service.cheltuieli_pe_categorie_luna_curenta(EU, valuta="RON")

    assert raspuns.categorii == []


@pytest.mark.anyio
async def test_cheltuieli_pe_categorie_exclude_lunile_anterioare() -> None:
    # 400 de zile in urma e mereu intr-o alta luna calendaristica, indiferent
    # de ziua in care ruleaza testul.
    service = AnalizaService(
        TranzactiiFalse([_tranzactie(400, 100.0, iesire=True, descriere="Kaufland veche")]),
        CarduriFalse([]),
    )

    raspuns = await service.cheltuieli_pe_categorie_luna_curenta(EU)

    assert raspuns.categorii == []
    assert raspuns.luna == ACUM.strftime("%Y-%m")


@pytest.mark.anyio
async def test_perioadele_cerute_sunt_plafonate() -> None:
    service = AnalizaService(TranzactiiFalse([]), CarduriFalse([]))

    assert len((await service.cashflow_lunar(EU, luni=999)).luni) <= 12
    assert len(await service.tranzactii_recente(EU, zile=99999, limita=999)) <= MAX_TRANZACTII_LISTATE

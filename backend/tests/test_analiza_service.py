from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.errors import ConfigurationError, ResourceNotFoundError, ValidationError
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

    async def obtine(self, tranzactie_id):
        return next((r for r in self.randuri if r["id"] == str(tranzactie_id)), None)


class CategoriiManualeFalse:
    def __init__(self, suprascrieri: dict[str, str] | None = None) -> None:
        self.suprascrieri = suprascrieri or {}
        self.scrise: list[tuple] = []

    async def pentru_tranzactii(self, tranzactie_ids):
        cerute = {str(id_) for id_ in tranzactie_ids}
        return {id_: cat for id_, cat in self.suprascrieri.items() if id_ in cerute}

    async def seteaza(self, id_tranzactie, id_user, categorie):
        self.scrise.append((str(id_tranzactie), str(id_user), categorie))
        self.suprascrieri[str(id_tranzactie)] = categorie


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


@pytest.mark.anyio
async def test_categoria_manuala_suprascrie_categorizeaza_in_cheltuieli_pe_categorie() -> None:
    """Raportat live: un transfer catre un comerciant necunoscut cade pe
    "altele", desi utilizatorul a confirmat explicit din asistent ca e
    "restaurant" — suprascrierea (0040) trebuie sa aiba prioritate."""
    tranzactie = _tranzactie(0, 100.0, iesire=True, descriere="Comerciant necunoscut XYZ")
    service = AnalizaService(
        TranzactiiFalse([tranzactie]),
        CarduriFalse([]),
        categorii_manuale=CategoriiManualeFalse({tranzactie["id"]: "restaurant"}),
    )

    raspuns = await service.cheltuieli_pe_categorie_luna_curenta(EU)

    assert len(raspuns.categorii) == 1
    assert raspuns.categorii[0].categorie == "restaurant"
    assert raspuns.categorii[0].total == 100.0


@pytest.mark.anyio
async def test_categoria_manuala_suprascrie_categorizeaza_in_tranzactii_recente() -> None:
    tranzactie = _tranzactie(0, 42.0, iesire=True, descriere="Comerciant necunoscut XYZ")
    service = AnalizaService(
        TranzactiiFalse([tranzactie]),
        CarduriFalse([]),
        categorii_manuale=CategoriiManualeFalse({tranzactie["id"]: "masina"}),
    )

    randuri = await service.tranzactii_recente(EU)

    assert randuri[0]["categorie"] == "masina"


@pytest.mark.anyio
async def test_fara_suprascriere_categorizeaza_ramane_implicitul() -> None:
    tranzactie = _tranzactie(0, 42.0, iesire=True, descriere="Comerciant necunoscut XYZ")
    service = AnalizaService(
        TranzactiiFalse([tranzactie]), CarduriFalse([]), categorii_manuale=CategoriiManualeFalse({}),
    )

    randuri = await service.tranzactii_recente(EU)

    assert randuri[0]["categorie"] == "altele"


@pytest.mark.anyio
async def test_seteaza_categorie_manuala_scrie_cand_tranzactia_apartine_utilizatorului() -> None:
    tranzactie = _tranzactie(0, 150.0, iesire=True, descriere="Cina la restaurant")
    categorii_manuale = CategoriiManualeFalse()
    service = AnalizaService(
        TranzactiiFalse([tranzactie]), CarduriFalse([]), categorii_manuale=categorii_manuale,
    )

    await service.seteaza_categorie_manuala(EU, tranzactie["id"], "restaurant")

    assert categorii_manuale.scrise == [(tranzactie["id"], str(EU), "restaurant")]


@pytest.mark.anyio
async def test_seteaza_categorie_manuala_respinge_o_categorie_necunoscuta() -> None:
    tranzactie = _tranzactie(0, 150.0, iesire=True)
    service = AnalizaService(
        TranzactiiFalse([tranzactie]), CarduriFalse([]), categorii_manuale=CategoriiManualeFalse(),
    )

    with pytest.raises(ValidationError):
        await service.seteaza_categorie_manuala(EU, tranzactie["id"], "categorie-inventata")


@pytest.mark.anyio
async def test_seteaza_categorie_manuala_respinge_o_tranzactie_care_nu_exista_sau_nu_e_a_lui() -> None:
    # TranzactiiFalse.obtine() simuleaza RLS: o tranzactie straina/inexistenta
    # nu se gaseste niciodata, indiferent de id_user dat aici.
    service = AnalizaService(
        TranzactiiFalse([]), CarduriFalse([]), categorii_manuale=CategoriiManualeFalse(),
    )

    with pytest.raises(ResourceNotFoundError):
        await service.seteaza_categorie_manuala(EU, str(uuid4()), "restaurant")


@pytest.mark.anyio
async def test_seteaza_categorie_manuala_fara_repository_e_o_eroare_de_configurare() -> None:
    tranzactie = _tranzactie(0, 150.0, iesire=True)
    service = AnalizaService(TranzactiiFalse([tranzactie]), CarduriFalse([]))

    with pytest.raises(ConfigurationError):
        await service.seteaza_categorie_manuala(EU, tranzactie["id"], "restaurant")

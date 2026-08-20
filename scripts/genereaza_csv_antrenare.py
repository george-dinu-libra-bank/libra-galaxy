"""Genereaza tranzactii sintetice in CSV, pentru antrenarea modelului.

Spre deosebire de seed_tranzactii.py, NU scrie nimic in baza de date: produce
fisiere pe disc, ca modelul sa poata fi antrenat fara cheia privilegiata si
fara sa depinda de cate tranzactii reale exista in cloud.

    python scripts/genereaza_csv_antrenare.py

Coloanele sunt exact cele citite de TranzactieRepository.CAMPURI, ca randurile
sa treaca neschimbate prin app.ml.caracteristici.normalizeaza().
"""

import argparse
import csv
import pathlib
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

RADACINA = pathlib.Path(__file__).resolve().parent.parent
DIRECTOR_DATE = RADACINA / "backend" / "data"

# (nume, suma minima, suma maxima, cate plati pe luna)
COMERCIANTI = [
    ("Kaufland", 45, 180, 6),
    ("Lidl", 30, 120, 5),
    ("Mega Image", 15, 70, 8),
    ("OMV benzina", 150, 320, 3),
    ("Glovo", 25, 90, 7),
    ("Farmacia Tei", 20, 110, 2),
    ("Carrefour", 40, 160, 4),
    ("Dedeman", 80, 400, 1),
]
ABONAMENTE = [("Netflix", 55.99, 12), ("Spotify", 24.99, 5), ("Digi internet", 45.00, 20)]

CAMPURI = [
    "id",
    "suma",
    "valuta",
    "descriere",
    "creat_la",
    "id_user_send",
    "id_user_recieve",
]


def _uuid(aleator: random.Random) -> str:
    return str(uuid.UUID(int=aleator.getrandbits(128), version=4))


def _rand(
    aleator: random.Random,
    moment: datetime,
    suma: float,
    descriere: str,
    expeditor: str | None,
    destinatar: str | None,
) -> dict:
    return {
        "id": _uuid(aleator),
        "suma": round(suma, 2),
        "valuta": "RON",
        "descriere": descriere,
        "creat_la": moment.isoformat(),
        "id_user_send": expeditor or "",
        "id_user_recieve": destinatar or "",
    }


def genereaza_utilizator(
    aleator: random.Random, user_id: str, luni: int, acum: datetime
) -> list[dict]:
    """Un an de cheltuieli obisnuite: salariu, abonamente, cumparaturi curente."""
    randuri: list[dict] = []
    # Fiecare utilizator are alt nivel de venit si alta inclinatie de cheltuiala,
    # ca modelul sa nu invete un singur tipar.
    salariu = round(aleator.uniform(4000, 14000), 2)
    factor = aleator.uniform(0.7, 1.4)

    zi = acum - timedelta(days=30 * luni)
    while zi < acum:
        if zi.day == 5:
            randuri.append(_rand(aleator, zi, salariu, "Salariu", None, user_id))

        for nume, suma, ziua in ABONAMENTE:
            if zi.day == ziua:
                randuri.append(_rand(aleator, zi, suma, nume, user_id, None))

        for nume, minim, maxim, pe_luna in COMERCIANTI:
            if aleator.random() < pe_luna / 30:
                moment = zi + timedelta(
                    hours=aleator.randint(8, 21), minutes=aleator.randint(0, 59)
                )
                randuri.append(
                    _rand(
                        aleator,
                        moment,
                        aleator.uniform(minim, maxim) * factor,
                        f"{nume} ref {aleator.randint(10000000, 99999999)}",
                        user_id,
                        None,
                    )
                )
        zi += timedelta(days=1)

    return randuri


def anomalii(aleator: random.Random, user_id: str, acum: datetime) -> list[tuple[dict, str]]:
    """Cele trei tipare pe care detectorul trebuie sa le prinda, cu eticheta lor."""
    dubla = acum - timedelta(days=5)
    return [
        (
            _rand(
                aleator,
                acum - timedelta(days=9),
                2450.00,
                "Kaufland ref 55512345",
                user_id,
                None,
            ),
            "suma_neobisnuita",
        ),
        (
            _rand(aleator, dubla, 349.90, "Emag ref 77712345", user_id, None),
            "",
        ),
        (
            _rand(
                aleator,
                dubla + timedelta(minutes=4),
                349.90,
                "Emag ref 77798765",
                user_id,
                None,
            ),
            "plata_dublata",
        ),
        (
            _rand(
                aleator,
                acum - timedelta(days=2),
                4200.00,
                "Bijuterii Lux ref 91112345",
                user_id,
                None,
            ),
            "comerciant_nou",
        ),
    ]


def _mediana(valori: list[float]) -> float:
    ordonate = sorted(valori)
    mijloc = len(ordonate) // 2
    if not ordonate:
        return 0.0
    if len(ordonate) % 2:
        return ordonate[mijloc]
    return (ordonate[mijloc - 1] + ordonate[mijloc]) / 2


def anomalii_subtile(
    aleator: random.Random, user_id: str, acum: datetime, istoric: list[dict]
) -> list[tuple[dict, str]]:
    """Tipare pe care cele trei reguli statistice nu au cum sa le prinda.

    Fara ele, stratul de model nu poate fi evaluat: regulile revendica primele
    orice caz clar (verificarile sunt inlantuite cu `or`), asa ca modelul ramane
    doar cu plati obisnuite pe care le poate semnala gresit.

    Fiecare tipar de aici e construit ca sa scape deliberat fiecarei reguli:
      - sume in jurul medianei comerciantului  -> _suma_atipica nu se declanseaza
      - sume diferite intre ele                -> _dubla_debitare nu se declanseaza
      - comerciant cunoscut, sau sub 300 RON   -> _comerciant_nou nu se declanseaza
    Ce ramane neobisnuit e ritmul, iar ritmul e in vectorul de trasaturi
    (`zile_de_la_ultima`), deci modelul are de unde sa il invete.
    """
    rezultat: list[tuple[dict, str]] = []

    # 1. Rafala: patru plati intr-o singura zi la un comerciant vizitat de obicei
    #    saptamanal. Sumele sunt normale; anormal e ca vin una dupa alta.
    sume_glovo = [
        float(r["suma"]) for r in istoric if r["descriere"].lower().startswith("glovo")
    ]
    tipic = _mediana(sume_glovo) if sume_glovo else 55.0
    ziua_rafalei = acum - timedelta(days=12)
    nr_plati = 4
    for i in range(nr_plati):
        moment = ziua_rafalei + timedelta(hours=9 + i * 2, minutes=aleator.randint(0, 59))
        rezultat.append(
            (
                _rand(
                    aleator,
                    moment,
                    tipic * aleator.uniform(0.9, 1.1),
                    f"Glovo ref {aleator.randint(10000000, 99999999)}",
                    user_id,
                    None,
                ),
                # Numai ultima plata e asteptata sa fie semnalata: pana la ea,
                # doua-trei plati intr-o zi inca nu sunt o rafala. O rafala
                # produce o alerta, nu cate una pentru fiecare plata din ea.
                "rafala" if i == nr_plati - 1 else "",
            )
        )

    # 2. Sume mici repetate la un comerciant nou — tiparul clasic de testare a
    #    unui card furat. Sub PRAG_SUMA_MINIMA, deci invizibil pentru reguli.
    ziua_testarii = acum - timedelta(days=6)
    for i in range(6):
        moment = ziua_testarii + timedelta(hours=1, minutes=i * 7 + aleator.randint(0, 4))
        rezultat.append(
            (
                _rand(
                    aleator,
                    moment,
                    aleator.uniform(2.5, 9.0),
                    f"DigitalGoods ref {aleator.randint(10000000, 99999999)}",
                    user_id,
                    None,
                ),
                "sume_mici_repetate" if i else "",
            )
        )

    return rezultat


def scrie(cale: pathlib.Path, randuri: list[dict], campuri: list[str]) -> None:
    cale.parent.mkdir(parents=True, exist_ok=True)
    with cale.open("w", encoding="utf-8", newline="") as fisier:
        scriitor = csv.DictWriter(fisier, fieldnames=campuri)
        scriitor.writeheader()
        scriitor.writerows(randuri)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--utilizatori", type=int, default=15)
    parser.add_argument("--luni", type=int, default=12)
    argumente = parser.parse_args()

    aleator = random.Random(42)
    acum = datetime.now(timezone.utc).replace(microsecond=0)

    # Antrenare: numai comportament obisnuit. Modelul invata "normalul"; ce iese
    # din el il marcheaza singur, dupa contamination.
    antrenare: list[dict] = []
    for _ in range(argumente.utilizatori):
        antrenare.extend(
            genereaza_utilizator(aleator, _uuid(aleator), argumente.luni, acum)
        )
    antrenare.sort(key=lambda r: r["creat_la"])

    # Testare: un utilizator obisnuit, anomaliile pe care le prind regulile, si
    # cele subtile, pe care numai modelul le poate prinde.
    user_test = _uuid(aleator)
    randuri_test = genereaza_utilizator(aleator, user_test, argumente.luni, acum)
    etichete = {r["id"]: "" for r in randuri_test}

    de_adaugat = anomalii(aleator, user_test, acum) + anomalii_subtile(
        aleator, user_test, acum, randuri_test
    )
    for rand, eticheta in de_adaugat:
        randuri_test.append(rand)
        etichete[rand["id"]] = eticheta
    randuri_test.sort(key=lambda r: r["creat_la"])

    scrie(DIRECTOR_DATE / "tranzactii_antrenare.csv", antrenare, CAMPURI)
    scrie(
        DIRECTOR_DATE / "tranzactii_testare.csv",
        [{**r, "anomalie_asteptata": etichete[r["id"]]} for r in randuri_test],
        [*CAMPURI, "anomalie_asteptata"],
    )

    iesiri = sum(1 for r in antrenare if r["id_user_send"])
    print(f"antrenare: {len(antrenare)} tranzactii ({iesiri} plati), {argumente.utilizatori} utilizatori")
    print(f"testare:   {len(randuri_test)} tranzactii, utilizator {user_test}")
    print(f"scrise in {DIRECTOR_DATE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

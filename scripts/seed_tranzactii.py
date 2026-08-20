"""Genereaza tranzactii realiste pentru un utilizator, ca sa fie ce analiza.

SCRIE IN BAZA DE DATE. Nu se ruleaza din greseala: cere explicit id-ul
utilizatorului si confirmarea.

    python scripts/seed_tranzactii.py --user <uuid> --luni 12 --confirm

Citeste SUPABASE_URL si SUPABASE_SERVICE_ROLE_KEY din backend/.env.
Genereaza salariu lunar, abonamente recurente, cumparaturi cu variatie
saptamanala si cateva anomalii deliberate, ca detectorul sa aiba ce gasi.
"""

import argparse
import json
import pathlib
import random
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

RADACINA = pathlib.Path(__file__).resolve().parent.parent

COMERCIANTI = [
    ("Kaufland", 45, 180, 6),
    ("Lidl", 30, 120, 5),
    ("Mega Image", 15, 70, 8),
    ("OMV benzina", 150, 320, 3),
    ("Glovo", 25, 90, 7),
    ("Farmacia Tei", 20, 110, 2),
]
ABONAMENTE = [("Netflix", 55.99, 12), ("Spotify", 24.99, 5), ("Digi internet", 45.00, 20)]
SALARIU = 8500.00


def mediu() -> tuple[str, str]:
    valori = {}
    for linie in (RADACINA / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        if linie.strip() and not linie.startswith("#") and "=" in linie:
            cheie, _, valoare = linie.partition("=")
            valori[cheie.strip()] = valoare.strip()
    url, cheie = valori.get("SUPABASE_URL", ""), valori.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not cheie:
        raise SystemExit("backend/.env nu are SUPABASE_URL si SUPABASE_SERVICE_ROLE_KEY.")
    return url.rstrip("/"), cheie


def genereaza(user_id: str, luni: int) -> list[dict]:
    aleator = random.Random(42)
    acum = datetime.now(timezone.utc)
    inceput = acum - timedelta(days=30 * luni)
    randuri: list[dict] = []

    def cheltuiala(moment: datetime, suma: float, descriere: str) -> None:
        randuri.append(
            {
                "id_user_send": user_id,
                "id_user_recieve": None,
                "suma": round(suma, 2),
                "valuta": "RON",
                "descriere": descriere,
                "creat_la": moment.isoformat(),
            }
        )

    zi = inceput
    while zi < acum:
        if zi.day == 5:
            randuri.append(
                {
                    "id_user_send": None,
                    "id_user_recieve": user_id,
                    "suma": SALARIU,
                    "valuta": "RON",
                    "descriere": "Salariu",
                    "creat_la": zi.isoformat(),
                }
            )
        for nume, suma, ziua in ABONAMENTE:
            if zi.day == ziua:
                cheltuiala(zi, suma, nume)
        for nume, minim, maxim, pe_luna in COMERCIANTI:
            if aleator.random() < pe_luna / 30:
                cheltuiala(
                    zi + timedelta(hours=aleator.randint(8, 21)),
                    aleator.uniform(minim, maxim),
                    f"{nume} ref {aleator.randint(10000000, 99999999)}",
                )
        zi += timedelta(days=1)

    # Anomalii deliberate, ca detectorul sa aiba ce gasi.
    recent = acum - timedelta(days=9)
    cheltuiala(recent, 2450.00, "Kaufland ref 55512345")          # suma atipica
    dubla = acum - timedelta(days=5)
    cheltuiala(dubla, 349.90, "Emag ref 77712345")                 # dubla debitare
    cheltuiala(dubla + timedelta(minutes=4), 349.90, "Emag ref 77798765")
    cheltuiala(acum - timedelta(days=2), 4200.00, "Bijuterii Lux ref 91112345")  # comerciant nou

    randuri.sort(key=lambda r: r["creat_la"])
    return randuri


def trimite(url: str, cheie: str, randuri: list[dict]) -> None:
    for start in range(0, len(randuri), 200):
        pachet = randuri[start : start + 200]
        cerere = urllib.request.Request(
            f"{url}/rest/v1/tranzactii",
            data=json.dumps(pachet).encode(),
            headers={
                "apikey": cheie,
                "Authorization": f"Bearer {cheie}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        with urllib.request.urlopen(cerere, timeout=60) as raspuns:
            print(f"  inserate {len(pachet)} (HTTP {raspuns.status})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True, help="uuid-ul din public.profiles")
    parser.add_argument("--luni", type=int, default=12)
    parser.add_argument("--confirm", action="store_true", help="fara asta doar afiseaza")
    argumente = parser.parse_args()

    url, cheie = mediu()
    randuri = genereaza(argumente.user, argumente.luni)
    iesiri = sum(1 for r in randuri if r["id_user_send"])

    print(f"{len(randuri)} tranzactii generate ({iesiri} plati) pe {argumente.luni} luni")
    print(f"tinta: {url}")

    if not argumente.confirm:
        print("\nNimic nu s-a scris. Adauga --confirm ca sa insereze.")
        return 0

    trimite(url, cheie, randuri)
    print("gata")
    return 0


if __name__ == "__main__":
    sys.exit(main())

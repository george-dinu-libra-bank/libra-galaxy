"""Pregateste un utilizator existent ca sa poata fi testat fluxul de creditare.

SCRIE IN BAZA DE DATE. Nu se ruleaza din greseala: cere id-ul utilizatorului,
scenariul si `--confirm`.

    python -m app.scripts.seed_credit_demo --user <uuid> --scenariu aprobat --confirm
    docker compose exec backend python -m app.scripts.seed_credit_demo --user <uuid> --scenariu gri --confirm

Ruda apropiata e scripts/seed_tranzactii.py, de la care imprumuta forma
tranzactiilor. Difera prin doua lucruri care conteaza pentru creditare:

1. **Venitul e parametrizat**, nu fix — cele trei scenarii se deosebesc tocmai
   prin cat castiga omul, iar detectorul din app/credit/venit.py trebuie sa
   gaseasca exact suma potrivita.
2. **Pregateste si restul conditiilor**: statusul de identitate verificata
   (creditarea il cere) si expunerile din registrul intern care tine locul
   Biroului de Credit.

Scenariile sunt calibrate ca sa cada in cele trei decizii posibile. Nu sunt
alese la intamplare: `gri` e dinadins la mijloc, ca sa se vada ca zona de
analiza manuala exista si nu e doar o ramura moarta in cod.
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.infrastructure.supabase_client import get_service_client

LUNI_ISTORIC = 14
ZIUA_SALARIULUI = 5

COMERCIANTI = [
    ("Kaufland", 45, 180, 6),
    ("Lidl", 30, 120, 5),
    ("Mega Image", 15, 70, 8),
    ("OMV benzina", 150, 320, 3),
    ("Glovo", 25, 90, 7),
]
ABONAMENTE = [("Netflix", 55.99, 12), ("Spotify", 24.99, 5), ("Digi internet", 45.00, 20)]


@dataclass(frozen=True, slots=True)
class Scenariu:
    nume: str
    salariu: float
    angajator: str
    rata_alta_banca: float
    asteptare: str
    sugestie: str


SCENARII = {
    "aprobat": Scenariu(
        nume="aprobat", salariu=8500.0, angajator="ACME Software SRL",
        rata_alta_banca=0.0, asteptare="aprobat automat",
        sugestie="30.000 RON pe 36 de luni",
    ),
    "gri": Scenariu(
        nume="gri", salariu=4200.0, angajator="Delta Logistic SRL",
        rata_alta_banca=400.0, asteptare="analiza manuala",
        sugestie="30.000 RON pe 48 de luni",
    ),
    "respins": Scenariu(
        nume="respins", salariu=2400.0, angajator="Mic Comert SRL",
        rata_alta_banca=300.0, asteptare="respins (venit sub minimul de 3.000 RON)",
        sugestie="20.000 RON pe 36 de luni",
    ),
}


def genereaza_tranzactii(user_id: str, salariu: float) -> list[dict]:
    """Salariu lunar plus cheltuieli, pe LUNI_ISTORIC luni in urma.

    Seed fix pentru random: doua rulari pe acelasi scenariu produc acelasi
    istoric, deci un rezultat surprinzator poate fi reprodus.

    Salariul are o variatie mica intre luni (cateva zeci de lei), fiindca un sir
    de sume identice la virgula ar fi mai curat decat orice extras de cont real,
    iar detectorul trebuie exersat pe ce va intalni efectiv.
    """
    aleator = random.Random(hash(user_id) % (2**31))
    acum = datetime.now(timezone.utc)
    randuri: list[dict] = []

    def cheltuiala(moment: datetime, suma: float, descriere: str) -> None:
        randuri.append({
            "id_user_send": user_id, "id_user_recieve": None,
            "suma": round(suma, 2), "valuta": "RON",
            "descriere": descriere, "creat_la": moment.isoformat(),
        })

    zi = acum - timedelta(days=30 * LUNI_ISTORIC)
    while zi < acum:
        if zi.day == ZIUA_SALARIULUI:
            randuri.append({
                "id_user_send": None, "id_user_recieve": user_id,
                "suma": round(salariu + aleator.uniform(-40, 40), 2), "valuta": "RON",
                "descriere": "Salariu", "creat_la": zi.isoformat(),
            })

        for nume, suma, ziua in ABONAMENTE:
            if zi.day == ziua:
                cheltuiala(zi, suma, nume)

        # Cheltuielile se scaleaza cu venitul: cine castiga 2.400 nu cheltuie ca
        # cel cu 8.500, iar un raport nerealist ar strica si detectia, si scorul.
        factor = salariu / 8500.0
        for nume, minim, maxim, pe_luna in COMERCIANTI:
            if aleator.random() < pe_luna / 30:
                cheltuiala(
                    zi + timedelta(hours=aleator.randint(8, 21)),
                    aleator.uniform(minim, maxim) * factor,
                    f"{nume} ref {aleator.randint(10000000, 99999999)}",
                )
        zi += timedelta(days=1)

    randuri.sort(key=lambda rand: rand["creat_la"])
    return randuri


def main() -> int:
    parser = argparse.ArgumentParser(description="Pregateste un utilizator pentru testarea creditarii.")
    parser.add_argument("--user", required=True, help="uuid-ul utilizatorului din public.profiles")
    parser.add_argument("--scenariu", required=True, choices=sorted(SCENARII))
    parser.add_argument("--confirm", action="store_true", help="fara asta nu scrie nimic")
    argumente = parser.parse_args()

    scenariu = SCENARII[argumente.scenariu]
    client = get_service_client()

    profil = (
        client.table("profiles")
        .select("id,nume,cnp,verification_status")
        .eq("id", argumente.user)
        .maybe_single()
        .execute()
    )
    date_profil = profil.data if profil else None
    if not date_profil:
        print(f"Nu exista niciun profil cu id-ul {argumente.user}.", file=sys.stderr)
        return 1

    tranzactii = genereaza_tranzactii(argumente.user, scenariu.salariu)
    incasari = sum(1 for rand in tranzactii if rand["id_user_recieve"])

    print(f"Profil     : {date_profil['nume']} ({date_profil['cnp']})")
    print(f"Scenariu   : {scenariu.nume} — salariu {scenariu.salariu:,.0f} RON la {scenariu.angajator}")
    print(f"Tranzactii : {len(tranzactii)} ({incasari} incasari de salariu pe {LUNI_ISTORIC} luni)")
    print(f"Obligatii  : {scenariu.rata_alta_banca:,.0f} RON/luna in registrul de expuneri")
    print(f"Identitate : {date_profil['verification_status']} -> verified")
    print(f"Asteptare  : {scenariu.asteptare}, la o cerere de {scenariu.sugestie}")

    if not argumente.confirm:
        print("\nNu s-a scris nimic. Adauga --confirm ca sa aplici.")
        return 0

    for indice in range(0, len(tranzactii), 200):
        client.table("tranzactii").insert(tranzactii[indice:indice + 200]).execute()

    # Creditarea cere identitate verificata (app/credit/reguli.py). Pe un cont de
    # test nu avem buletin si selfie, deci se seteaza direct statusul rezumat.
    client.table("profiles").update({"verification_status": "verified"}).eq("id", argumente.user).execute()

    client.table("credit_bureau_simulat").delete().eq("cnp", date_profil["cnp"]).execute()
    if scenariu.rata_alta_banca > 0:
        client.table("credit_bureau_simulat").insert({
            "cnp": date_profil["cnp"], "banca": "Banca Transilvania",
            "tip_produs": "nevoi personale",
            "rata_lunara": scenariu.rata_alta_banca,
            "sold": round(scenariu.rata_alta_banca * 24, 2),
        }).execute()

    print("\nGata. Verifica fluxul complet cu:")
    print(f"  python -m app.scripts.verifica_flux_credit --user {argumente.user}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

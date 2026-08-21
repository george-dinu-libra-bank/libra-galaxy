"""Ruleaza tot lantul de creditare pe baza reala si tipareste fiecare pas.

    python -m app.scripts.verifica_flux_credit --user <uuid>
    python -m app.scripts.verifica_flux_credit --user <uuid> --suma 30000 --luni 36 --curata

E verificarea de nivel 3 din REGULI.md #7: apel live, cu credentiale reale. Ce
prinde si ce nu prinde `pytest`:

- pytest verifica formulele (graficul se inchide pe zero, scorul e monoton);
- asta verifica lantul — ca RPC-ul chiar muta banii, ca detectorul chiar gaseste
  salariul in tranzactiile reale, ca RLS nu blocheaza scrierea, ca tipurile
  numeric(14,2) din Postgres se intorc in Decimal fara pierderi.

Nu foloseste SQL direct nicaieri: trece prin exact acelasi CreditService pe care
il apeleaza rutele HTTP. Daca scriptul asta merge, si API-ul merge.

`--curata` sterge la final cererea si creditul create, dar NU si tranzactiile de
virament si de rata — ele sunt istoric bancar, iar stergerea lor ar lasa soldul
contului fara explicatie. Soldul revine oricum la valoarea initiala doar daca
rulezi rambursarea integrala, fiindca dobanda platita e cost real.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from uuid import UUID

from app.credit.venit import detecteaza_venit
from app.infrastructure.supabase_client import get_service_client
from app.ml.caracteristici import normalizeaza
from app.ml.neregularitati import DetectorNeregularitati
from app.repositories.credit_repository import CreditRepository
from app.services.credit_service import CreditService

LATIME = 78

# Consola Windows implicita e cp1252 si nu poate scrie diacritice sau
# caractere de desen — scriptul cadea cu UnicodeEncodeError inainte sa
# apuce sa afiseze ceva. Trecem iesirea pe UTF-8; unde terminalul tot nu
# poate reda un caracter, "replace" pune un semn de intrebare in loc sa
# opreasca verificarea.
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")


def titlu(text: str) -> None:
    print(f"\n{text}\n{'-' * min(len(text), LATIME)}")


def rand(eticheta: str, valoare) -> None:
    print(f"  {eticheta:<26} {valoare}")


async def ruleaza(user_id: UUID, suma: Decimal, luni: int, avans: int, curata: bool) -> int:
    depozit = CreditRepository(get_service_client())
    serviciu = CreditService(depozit, DetectorNeregularitati.cu_model_de_pe_disc())

    profil = await depozit.profil(user_id)
    if not profil:
        print(f"Nu exista niciun profil cu id-ul {user_id}.", file=sys.stderr)
        return 1

    titlu("0. SOLICITANT")
    rand("Nume", profil["nume"])
    rand("Identitate", profil["verification_status"])
    conturi = [c for c in await depozit.conturi(user_id) if c["valuta"] == "RON"]
    if not conturi:
        print("Nu are niciun cont in RON; creditul se vireaza numai in RON.", file=sys.stderr)
        return 1
    cont = conturi[0]
    rand("Cont de creditare", f"{cont['iban'][-8:]} - sold {Decimal(str(cont['sold'])):,.2f} RON")

    # Ce vede detectorul, inainte de orice cerere — util cand rezultatul surprinde.
    randuri = await depozit.tranzactii_pentru_venit(user_id)
    constatat = detecteaza_venit(normalizeaza(randuri, user_id))
    if constatat:
        rand("Venit detectat", f"{constatat.venit_lunar:,.2f} RON de la {constatat.platitor!r}")
        rand("", f"{constatat.luni_detectate} incasari, deviatie {constatat.deviatie_relativa:.2%}, "
                 f"incredere {constatat.incredere:.0%}")
    else:
        rand("Venit detectat", "niciun tipar recurent gasit in tranzactii")

    titlu("1. SIMULARE")
    simulare = await serviciu.simuleaza(suma, luni)
    rand("Credit", f"{simulare.suma:,.2f} RON pe {simulare.luni} luni")
    rand("Dobanda", f"{simulare.dobanda_anuala:.2%} fix")
    rand("Rata lunara", f"{simulare.rata_lunara:,.2f} RON")
    rand("DAE", f"{simulare.dae:.2%}")
    rand("Cost total", f"{simulare.cost_total:,.2f} RON")

    titlu("2. CERERE")
    cerere = await serviciu.depune_cerere(user_id, {
        "suma": suma, "luni": luni,
        "venit_declarat": Decimal(str(constatat.venit_lunar)) if constatat else Decimal("5000"),
        "angajator": "Angajator declarat", "vechime_angajator_luni": 24,
        "obligatii_declarate": Decimal(0), "scop": "verificare flux",
    })
    rand("Cerere", cerere["id"])

    titlu("3. VERIFICARI SI DECIZIE")
    decizie = await serviciu.evalueaza(UUID(cerere["id"]), user_id)

    for verificare in await depozit.verificari(UUID(cerere["id"])):
        detaliu = verificare["venit_constatat"] or verificare["obligatii_constatate"] or "-"
        rand(f"sursa: {verificare['sursa']}", f"{detaliu}  (incredere {verificare['incredere']})")

    print()
    rand("DTI", f"{decizie.dti:.2%}" if decizie.dti is not None else "-")
    rand("Scor", f"{decizie.scor}/100" if decizie.scor is not None else "-")
    rand("DECIZIE", decizie.decizie.upper())

    for factor in decizie.factori:
        rand(f"  {factor['cod']}", f"{factor['puncte']:>3}/{factor['maxim']:<3} {factor['explicatie']}")
    for motiv in decizie.motive:
        rand(f"  {motiv['cod']}", motiv["text"])

    print(f"\n{decizie.explicatie}\n")

    if decizie.decizie != "aprobat":
        print("Fluxul se opreste aici - cererea nu a fost aprobata, ceea ce e un rezultat valid.")
        if curata:
            await _curata(cerere["id"], None)
        return 0

    titlu("4. ACORDARE")
    acordare = await serviciu.accepta(
        UUID(cerere["id"]), user_id, UUID(cont["id"]),
        {"ip": "script", "user_agent": "verifica_flux_credit"},
    )
    rand("Credit acordat", acordare["id_credit"])
    rand("Virat in cont", f"{Decimal(str(acordare['principal'])):,.2f} RON")
    rand("Sold cont nou", f"{Decimal(str(acordare['sold_cont_nou'])):,.2f} RON")
    rand("Prima scadenta", acordare["prima_scadenta"])

    id_credit = UUID(acordare["id_credit"])

    titlu(f"5. RATE (avans simulat de {avans} luni)")
    detaliu = await serviciu.avanseaza_timp(id_credit, user_id, avans)
    rand("Rate platite", f"{detaliu['rate_platite']} din {detaliu['credit']['luni']}")
    rand("Sold ramas", f"{Decimal(str(detaliu['credit']['sold_ramas'])):,.2f} RON")
    rand("Stare credit", detaliu["credit"]["status"])
    if detaliu["urmatoarea_rata"]:
        urmatoarea = detaliu["urmatoarea_rata"]
        rand("Urmatoarea rata", f"#{urmatoarea['numar_rata']} pe {urmatoarea['scadenta']}, "
                                f"{Decimal(str(urmatoarea['rata_totala'])):,.2f} RON")

    titlu("6. RAMBURSARE ANTICIPATA")
    calcul = await serviciu.calcul_rambursare(id_credit, user_id)
    rand("Sold de stins", f"{calcul['sold']:,.2f} RON")
    rand("Dobanda acumulata", f"{calcul['dobanda_acumulata']:,.2f} RON")
    rand("Total de plata", f"{calcul['total_de_plata']:,.2f} RON")
    rand("Economie de dobanda", f"{calcul['economie_dobanda']:,.2f} RON")

    rezultat = await serviciu.ramburseaza(id_credit, user_id)
    print()
    rand("Platit", f"{Decimal(str(rezultat['total_platit'])):,.2f} RON")
    rand("Sold ramas", f"{Decimal(str(rezultat['sold_ramas'])):,.2f} RON")
    rand("Stare finala", rezultat["status"])
    rand("Sold cont", f"{Decimal(str(rezultat['sold_cont'])):,.2f} RON")

    titlu("REZULTAT")
    reusit = rezultat["status"] == "rambursat_anticipat" and Decimal(str(rezultat["sold_ramas"])) == 0
    print("  Lantul complet a mers: simulare -> cerere -> verificari -> decizie ->")
    print("  acordare -> virament -> rate incasate -> rambursare -> credit stins.")
    if not reusit:
        print("\n  ATENTIE: creditul nu s-a inchis cum trebuia.", file=sys.stderr)

    if curata:
        await _curata(cerere["id"], acordare["id_credit"])
    return 0 if reusit else 1


async def _curata(id_cerere: str, id_credit: str | None) -> None:
    """Sterge cererea si creditul. Tranzactiile raman — sunt istoric bancar."""
    client = get_service_client()
    if id_credit:
        client.table("credite").delete().eq("id", id_credit).execute()
    client.table("credit_cereri").delete().eq("id", id_cerere).execute()
    print("\n  Curatat: cererea si creditul sterse. Tranzactiile raman in istoric.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica live tot fluxul de creditare.")
    parser.add_argument("--user", required=True)
    parser.add_argument("--suma", type=Decimal, default=Decimal("30000"))
    parser.add_argument("--luni", type=int, default=36)
    parser.add_argument("--avans", type=int, default=3, help="cate luni sa avanseze pentru rate")
    parser.add_argument("--curata", action="store_true", help="sterge cererea si creditul la final")
    argumente = parser.parse_args()

    return asyncio.run(ruleaza(
        UUID(argumente.user), argumente.suma, argumente.luni, argumente.avans, argumente.curata
    ))


if __name__ == "__main__":
    raise SystemExit(main())

"""Ruleaza detectorul pe setul de testare si compara cu anomaliile asteptate.

    python scripts/evalueaza_model.py

Se ruleaza dupa antrenare, ca sa se vada daca modelul chiar adauga ceva peste
baza statistica. Coloana anomalie_asteptata din CSV e folosita numai aici, la
evaluare — niciodata la antrenare.
"""

import csv
import pathlib
import sys

RADACINA = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADACINA / "backend"))

from app.ml.caracteristici import normalizeaza  # noqa: E402
from app.ml.neregularitati import CALE_MODEL, DetectorNeregularitati  # noqa: E402

CALE_TESTARE = RADACINA / "backend" / "data" / "tranzactii_testare.csv"

# Anomaliile pe care regulile statistice le prind singure. Restul etichetelor
# sunt tipare construite ca sa scape regulilor: numai modelul le poate prinde,
# si numai pe ele se vede daca stratul de model isi merita locul.
TIPURI_STATISTICE = {"suma_neobisnuita", "plata_dublata", "comerciant_nou", "rafala"}


def main() -> int:
    if not CALE_TESTARE.exists():
        raise SystemExit(f"Lipseste {CALE_TESTARE}. Ruleaza genereaza_csv_antrenare.py.")

    with CALE_TESTARE.open(encoding="utf-8", newline="") as fisier:
        randuri = list(csv.DictReader(fisier))

    asteptate = {r["id"]: r["anomalie_asteptata"] for r in randuri if r["anomalie_asteptata"]}
    user_id = next(r["id_user_send"] for r in randuri if r["id_user_send"])

    from uuid import UUID

    plati = normalizeaza(randuri, UUID(user_id))

    clasice = {i: t for i, t in asteptate.items() if t in TIPURI_STATISTICE}
    subtile = {i: t for i, t in asteptate.items() if t not in TIPURI_STATISTICE}

    print(f"{len(randuri)} tranzactii, {len(asteptate)} anomalii asteptate")
    print(f"  {len(clasice)} pe care regulile le prind singure")
    print(f"  {len(subtile)} construite ca sa scape regulilor (numai modelul le poate prinde)\n")

    for eticheta, detector in (
        ("fara model (doar baza statistica)", DetectorNeregularitati(model=None)),
        ("cu model antrenat", DetectorNeregularitati.cu_model_de_pe_disc()),
    ):
        if eticheta.startswith("cu model") and not CALE_MODEL.exists():
            print("cu model antrenat: model.joblib lipseste, sar peste")
            continue

        constatari = detector.evalueaza(plati)
        gasite = {c.id_tranzactie: c for c in constatari}
        prinse = [id for id, tip in asteptate.items() if id in gasite]

        pe_tip: dict[str, list[float]] = {}
        for c in constatari:
            pe_tip.setdefault(c.tip, []).append(c.scor)

        prinse_clasice = sum(1 for i in clasice if i in gasite)
        prinse_subtile = sum(1 for i in subtile if i in gasite)

        print(f"--- {eticheta} ---")
        print(f"constatari totale: {len(constatari)}")
        print(f"anomalii prinse:   {len(prinse)}/{len(asteptate)}")
        print(f"  clasice: {prinse_clasice}/{len(clasice)}")
        print(f"  subtile: {prinse_subtile}/{len(subtile)}   <- aici se vede modelul")
        for tip, scoruri in sorted(pe_tip.items()):
            print(f"  {tip:18} {len(scoruri):3} scor {min(scoruri):6.2f} .. {max(scoruri):6.2f}")

        for id_tranzactie, tip_asteptat in sorted(asteptate.items(), key=lambda x: x[1]):
            constatare = gasite.get(id_tranzactie)
            stare = "PRINSA" if constatare else "RATATA"
            detaliu = f"{constatare.tip} scor={constatare.scor}" if constatare else "-"
            print(f"  [{stare}] asteptat={tip_asteptat or '(parte dintr-un tipar)':24} {detaliu}")

        fals_pozitive = [c for id, c in gasite.items() if id not in asteptate]
        print(f"semnalari in plus: {len(fals_pozitive)}")
        for c in fals_pozitive[:5]:
            print(f"  {c.tip:18} {c.suma:9.2f} {c.comerciant[:28]:30} scor={c.scor}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

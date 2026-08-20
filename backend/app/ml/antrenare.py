"""Antreneaza modelul de neregularitati si salveaza artefactul.

Se ruleaza manual, nu la fiecare cerere:

    python -m app.ml.antrenare
    python -m app.ml.antrenare --csv backend/data/tranzactii_antrenare.csv

Fara --csv citeste tranzactiile cu cheia privilegiata (deci pe toti utilizatorii,
ca sa aiba de unde invata ce inseamna "normal"). Cu --csv citeste un fisier
generat de scripts/genereaza_csv_antrenare.py, ca modelul sa poata fi antrenat
si fara acces privilegiat la baza de date.

Rezultatul e app/ml/model.joblib. Daca fisierul lipseste, detectia ramane pe baza
statistica si aplicatia merge mai departe.
"""

import argparse
import csv
import json
import os
import pathlib
import sys
import urllib.request
from uuid import UUID

from app.ml.caracteristici import Plata, normalizeaza, vector
from app.ml.neregularitati import CALE_MODEL

MIN_EXEMPLE = 50

# Cat din date consideram atipic. Nu e o estimare a ratei de frauda: e chiar
# procentul pe care IsolationForest il va semnala, oricat de curate ar fi datele.
# Masurat pe setul de testare, cu trasaturile de acum: 0.01 prinde 0 din cele 8
# anomalii subtile, 0.02 prinde 5, iar 0.05 tot 5 dar cu de doua ori mai multe
# semnalari gresite. 0.02 e punctul de dupa care cresterea aduce numai zgomot.
CONTAMINARE = 0.02


def _descarca() -> list[dict]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    cheie = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not cheie:
        raise SystemExit("Am nevoie de SUPABASE_URL si SUPABASE_SERVICE_ROLE_KEY in mediu.")

    cerere = urllib.request.Request(
        f"{url}/rest/v1/tranzactii"
        "?select=id,suma,valuta,descriere,creat_la,id_user_send,id_user_recieve",
        headers={"apikey": cheie, "Authorization": f"Bearer {cheie}"},
    )
    with urllib.request.urlopen(cerere, timeout=60) as raspuns:
        return json.loads(raspuns.read().decode())


def _din_csv(cale: pathlib.Path) -> list[dict]:
    """Aceeasi forma de randuri ca _descarca, citita dintr-un fisier.

    Coloanele in plus (de exemplu anomalie_asteptata din setul de testare) nu
    deranjeaza: normalizeaza() ia doar ce ii trebuie.
    """
    if not cale.exists():
        raise SystemExit(f"Nu gasesc fisierul {cale}.")

    with cale.open(encoding="utf-8", newline="") as fisier:
        randuri = list(csv.DictReader(fisier))

    # Un rand fara suma sau fara data nu poate produce un vector; il sarim aici,
    # ca sa nu para mai tarziu ca modelul a invatat din date pe care nu le-a vazut.
    return [rand for rand in randuri if rand.get("suma") and rand.get("creat_la")]


def _exemple(randuri: list[dict]) -> list[list[float]]:
    """Un vector pentru fiecare plata de iesire, in contextul comerciantului ei."""
    pe_utilizator: dict[str, list[dict]] = {}
    for rand in randuri:
        expeditor = rand.get("id_user_send")
        if expeditor:
            pe_utilizator.setdefault(str(expeditor), []).append(rand)

    exemple: list[list[float]] = []
    for id_user, ale_lui in pe_utilizator.items():
        plati = [p for p in normalizeaza(ale_lui, UUID(id_user)) if p.iesire]
        grupuri: dict[str, list[Plata]] = {}
        for plata in plati:
            grupuri.setdefault(plata.comerciant, []).append(plata)
        # `plati` merge intreg ca referinta generala: vector() taie singur ce e
        # dupa momentul platii evaluate, deci modelul nu vede viitorul.
        #
        # Prima plata la un comerciant e sarita: la inferenta detectorul n-o
        # trimite la model (are regula ei, _comerciant_nou), deci nici antrenarea
        # nu trebuie sa contina asemenea vectori. Altfel modelul ar invata un
        # tipar pe care nu-l va intalni niciodata.
        exemple.extend(
            vector(plata, grupuri[plata.comerciant], plati)
            for plata in plati
            if any(p.moment < plata.moment for p in grupuri[plata.comerciant])
        )
    return exemple


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        type=pathlib.Path,
        default=None,
        help="fisier cu tranzactii; fara el se citeste din Supabase",
    )
    argumente = parser.parse_args()

    randuri = _din_csv(argumente.csv) if argumente.csv else _descarca()
    exemple = _exemple(randuri)
    print(f"{len(randuri)} tranzactii, {len(exemple)} exemple de antrenare")

    if len(exemple) < MIN_EXEMPLE:
        print(
            f"Prea putine date (minim {MIN_EXEMPLE}). Ruleaza intai "
            "scripts/genereaza_csv_antrenare.py sau scripts/seed_tranzactii.py."
        )
        return 1

    import joblib
    from sklearn.ensemble import IsolationForest

    # Fara etichete de frauda, problema e detectie de outlieri, nu clasificare
    # supervizata. contamination fixeaza ce procent consideram atipic.
    model = IsolationForest(n_estimators=200, contamination=CONTAMINARE, random_state=42)
    model.fit(exemple)

    joblib.dump(model, CALE_MODEL)
    print(f"model salvat in {CALE_MODEL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

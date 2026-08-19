"""Antreneaza modelul de neregularitati si salveaza artefactul.

Se ruleaza manual, nu la fiecare cerere:

    python -m app.ml.antrenare

Citeste tranzactiile cu cheia privilegiata (deci pe toti utilizatorii, ca sa aiba
de unde invata ce inseamna "normal") si scrie app/ml/model.joblib. Daca fisierul
lipseste, detectia ramane pe baza statistica si aplicatia merge mai departe.
"""

import json
import os
import sys
import urllib.request
from uuid import UUID

from app.ml.caracteristici import Plata, normalizeaza, vector
from app.ml.neregularitati import CALE_MODEL

MIN_EXEMPLE = 50


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
        exemple.extend(vector(plata, grupuri[plata.comerciant]) for plata in plati)
    return exemple


def main() -> int:
    randuri = _descarca()
    exemple = _exemple(randuri)
    print(f"{len(randuri)} tranzactii, {len(exemple)} exemple de antrenare")

    if len(exemple) < MIN_EXEMPLE:
        print(
            f"Prea putine date (minim {MIN_EXEMPLE}). Ruleaza intai "
            "scripts/seed_tranzactii.py sau foloseste doar baza statistica."
        )
        return 1

    import joblib
    from sklearn.ensemble import IsolationForest

    # Fara etichete de frauda, problema e detectie de outlieri, nu clasificare
    # supervizata. contamination fixeaza ce procent consideram atipic.
    model = IsolationForest(n_estimators=200, contamination=0.03, random_state=42)
    model.fit(exemple)

    joblib.dump(model, CALE_MODEL)
    print(f"model salvat in {CALE_MODEL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

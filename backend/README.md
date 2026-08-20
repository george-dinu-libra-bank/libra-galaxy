# Libra API

API FastAPI cu autentificare Supabase. Rutele sunt subtiri, iar accesul la date
ramane separat in `repositories/` si `services/`.

## Pornire locala

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
copy .env.example .env
.venv/Scripts/uvicorn app.main:app --reload
```

Endpoint-uri initiale:

- `GET /api/v1/health` - public;
- `GET /api/v1/me/profile` - necesita `Authorization: Bearer <Supabase access token>`.

Swagger este disponibil la `http://localhost:8000/docs` in afara mediului production.

## Modelul de neregularitati

`GET /api/v1/alerte` are doua straturi (vezi `app/ml/neregularitati.py`): o baza
statistica ce merge din prima zi, si un IsolationForest optional. Artefactul
`app/ml/model.joblib` **nu e in git** — se regenereaza:

```bash
# date sintetice, fara acces la baza de date
python ../scripts/genereaza_csv_antrenare.py
python -m app.ml.antrenare --csv data/tranzactii_antrenare.csv

# sau din tranzactiile reale, cu cheia privilegiata in mediu
python -m app.ml.antrenare
```

Cat timp artefactul lipseste, aplicatia merge mai departe pe baza statistica.
`python ../scripts/evalueaza_model.py` compara cele doua straturi pe setul de
testare si arata ce adauga modelul.

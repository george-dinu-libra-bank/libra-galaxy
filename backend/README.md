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

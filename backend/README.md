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

Endpoint-uri:

- `GET /api/v1/health` - public;
- `GET /api/v1/me/profile` - necesita `Authorization: Bearer <Supabase access token>`;
- `POST /api/v1/agents/chat` - asistentul financiar, acelasi tip de autentificare.

## Layer-ul de agenti

`POST /api/v1/agents/chat` primeste `{ "mesaj": "...", "istoric": [...] }` si intoarce
raspunsul plus lista de tool-uri apelate.

Cum e legat, conform capitolelor 7-9 din `ARCHITECTURE.md`:

```
ruta -> SpendingAgent -> tool -> SpendingService -> repository -> Supabase
```

- `user_id` nu este parametru de tool. Tool-urile din `app/tools/financial_tools.py`
  sunt inchideri peste contextul autentificat, deci modelul nu poate cere datele
  altui utilizator nici daca i se sugereaza asta in mesaj.
- Clientul Supabase e cel al utilizatorului (anon key + tokenul lui), asa ca RLS
  ramane bariera din baza de date.
- Agentul primeste sume agregate (`SpendingService`), nu tabele brute.
- Nu exista tool care sa modifice stare financiara. Transferurile si blocarea
  cardului raman in afara agentului.

Configurare: `ANTHROPIC_API_KEY` in `.env`. Fara ea ruta raspunde `503`, restul
API-ului functioneaza normal.

Swagger este disponibil la `http://localhost:8000/docs` in afara mediului production.

# Libra Galaxy

Aplicatie bancara demonstrativa: Next.js, FastAPI si Supabase local.

## Tot stack-ul in Docker

Ai nevoie doar de Docker Desktop si PowerShell. Scriptul construieste un container
utilitar cu Node.js, `npx` si Supabase CLI, porneste Supabase local, preia cheia anon
fara sa o salveze in repository, apoi construieste frontend-ul si backend-ul.
Edge Runtime nu este pornit, deoarece proiectul nu contine Edge Functions.

```powershell
.\scripts\dev-up.ps1
```

Servicii:

- frontend: `http://localhost:3000`;
- FastAPI / Swagger: `http://localhost:8000/docs`;
- Supabase API: `http://localhost:54321`;
- Supabase Studio: `http://localhost:54323`;
- PostgreSQL: `localhost:54322`.

Oprire:

```powershell
.\scripts\dev-down.ps1
```

Vezi [frontend/README.md](frontend/README.md), [backend/README.md](backend/README.md)
si [supabase/README.md](supabase/README.md) pentru rulare separata.

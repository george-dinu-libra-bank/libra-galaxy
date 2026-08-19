# Supabase local

Configuratia foloseste Supabase CLI, care porneste serviciile oficiale in
containere Docker si aplica automat fisierele din `migrations/`.

CLI-ul ruleaza intr-un container, fara Node.js sau `npx` instalat pe Windows:

```powershell
.\scripts\supabase.ps1 start
.\scripts\supabase.ps1 status
```

API-ul local este pe `http://localhost:54321`, PostgreSQL pe portul `54322`,
Studio pe `http://localhost:54323`, iar Inbucket pe `http://localhost:54324`.

Pentru resetarea bazei locale si reaplicarea migrarilor:

```powershell
.\scripts\supabase.ps1 db reset
```

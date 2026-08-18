# Libra – Frontend

Schelet Next.js 16 (App Router) cu TypeScript, Tailwind CSS 4 si ESLint 9 (flat config).

## Cerinte

- Node.js >= 20.9

## Pornire

```bash
npm install
npm run dev
```

Aplicatia porneste pe http://localhost:3000.

## Scripturi

| Comanda             | Descriere                          |
| ------------------- | ---------------------------------- |
| `npm run dev`       | server de dezvoltare (Turbopack)   |
| `npm run build`     | build de productie                 |
| `npm run start`     | ruleaza build-ul de productie      |
| `npm run lint`      | ESLint                             |
| `npm run typecheck` | verificare de tipuri (tsc)         |

## Structura

```
src/
  app/
    page.tsx              # landing
    login/                # autentificare
    register/             # inregistrare (nume, CNP, telefon, email, parola)
    dashboard/            # ecran protejat, citeste public.profiles
    auth/callback/        # schimba codul din emailurile Supabase pe sesiune
  components/
    auth/                 # AuthShell, formulare, drawere de auth
    dashboard/            # drawerul cu detaliile contului
    ui/                   # Button, Camp, Checkbox, Drawer (vaul), Banda
  lib/
    actions/auth.ts       # server actions: login, register, reset, logout
    supabase/             # client browser / server / middleware
    validare.ts           # CNP, telefon, email, parola
    iban.ts               # generare si validare IBAN (ISO 13616)
  middleware.ts           # reimprospatare sesiune + protejare rute
public/                   # fisiere statice
```

Regulile de design (culori, componente, cand se foloseste un drawer vaul) sunt in
[`../DESIGN.md`](../DESIGN.md).

## Variabile de mediu

Copiaza `.env.example` in `.env.local` si completeaza cheile din Supabase
(Project Settings → API).

## Supabase

1. Ruleaza `supabase/migrations/0001_profiles.sql` in SQL Editor-ul proiectului.
   Creeaza tabela `public.profiles`, politicile RLS si trigger-ul
   `on_auth_user_created` de pe `auth.users`.
2. La inregistrare, `signUp` trimite `nume`, `cnp`, `telefon` si `iban_cont` prin
   `options.data` (adica `raw_user_meta_data`); trigger-ul le copiaza in
   `public.profiles` impreuna cu emailul din `auth.users`.
3. In Authentication → Providers → Email alegi daca e nevoie de confirmare pe email.
   Interfata trateaza ambele cazuri: cu confirmare afiseaza mesajul de verificare,
   fara confirmare duce direct in `/dashboard`.
4. In Authentication → URL Configuration adauga `http://localhost:3000/auth/callback`
   la Redirect URLs.

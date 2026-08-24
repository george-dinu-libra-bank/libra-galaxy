-- =============================================================================
-- 0019 — sectiunea de securitate din setari
--
-- Doua lucruri care nu existau deloc: un comutator prin care omul isi poate
-- opri login-ul biometric, si evidenta dispozitivelor de pe care s-a intrat in
-- cont.
--
-- DE CE O TABELA PROPRIE DE DISPOZITIVE, cand Supabase are deja auth.sessions:
-- toate login-urile aplicatiei se fac in server actions (lib/actions/auth.ts),
-- deci GoTrue vede cererea venind de la containerul Next.js, nu de la browser.
-- `auth.sessions.ip` si `auth.sessions.user_agent` ar contine adresa si agentul
-- containerului — aceleasi pentru toata lumea, inutile pe un ecran de
-- securitate. Singurul loc unde datele reale ale browserului exista e antetul
-- cererii catre server action, deci acolo le citim si aici le scriem. In plus,
-- auth.sessions nu e expusa prin PostgREST si auth-js 2.109 n-are listSessions,
-- deci nici n-am putea-o citi.
--
-- Migrarea e ADITIVA si idempotenta: se poate rula de doua ori fara alt efect.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Oprirea login-ului biometric
--
-- Impunerea reala e in backend (services/identity_service.py, verifica_login_fata):
-- ruta /api/identity/login-match e neautentificata si accesibila direct, nu doar
-- prin proxy-ul Next.js, deci o verificare in frontend n-ar fi o bariera.
--
-- Coloana NU e protejata de triggerul profiles_protejeaza_campuri, deliberat: e
-- preferinta omului, iar politica "profil propriu: update" (0001) ii da voie
-- s-o schimbe. Ar trebui protejata doar daca ar deveni un blocaj impus de
-- administrator dupa o frauda — atunci nu mai are voie s-o dea singur inapoi.
-- -----------------------------------------------------------------------------
alter table public.profiles
  add column if not exists biometrie_activata boolean not null default true;

comment on column public.profiles.biometrie_activata is
  'False = login-ul cu fata e refuzat pentru acest cont, chiar daca exista un selfie verificat. '
  'Implicit true, ca sa nu se schimbe comportamentul conturilor existente.';


-- -----------------------------------------------------------------------------
-- 2. Dispozitivele conectate
--
-- UN RAND = UN DISPOZITIV, NU O SESIUNE.
-- Cheia e (id_user, amprenta), unde amprenta e iesirea normalizata a
-- parserului din frontend/src/lib/dispozitive.ts ("chrome|windows|desktop").
--
-- Alternativa evidenta ar fi fost cheia pe session_id-ul din JWT. Ar fi fost
-- exacta, dar ar fi produs un rand nou la fiecare re-login pe acelasi
-- calculator, iar cel vechi ar fi ramas afisat ca dispozitiv "conectat" fara
-- sa mai fie — si re-loginul e cel mai frecvent lucru care se intampla aici.
--
-- Compromisul acceptat, ca sa fie scris: doua laptopuri Windows cu Chrome apar
-- ca un singur rand. Pentru un cont personal (laptop + telefon) e alegerea
-- buna; pentru o banca adevarata n-ar fi.
--
-- Nu exista coloana de IP. In deploymentul actual (docker compose publica
-- 3000:3000 direct, fara reverse proxy) nu exista niciun antet X-Forwarded-For,
-- iar Next 16 nu expune adresa peer. Un IP afisat ar fi ori gol, ori — dupa ce
-- apare un proxy — o valoare pe care o poate falsifica clientul, exact pe
-- ecranul unde asta conteaza cel mai mult.
-- -----------------------------------------------------------------------------
create table if not exists public.dispozitive_conectate (
  id                uuid primary key default gen_random_uuid(),
  id_user           uuid not null references public.profiles (id) on delete cascade,

  amprenta          text not null,
  eticheta          text not null,
  agent_utilizator  text,
  mobil             boolean not null default false,

  id_sesiune        uuid,

  creat_la          timestamptz not null default now(),
  ultima_activitate timestamptz not null default now(),

  constraint dispozitive_conectate_unic unique (id_user, amprenta)
);

comment on table public.dispozitive_conectate is
  'Un rand per dispozitiv de pe care s-a intrat in cont. Populata din server actions, nu de GoTrue — vezi antetul migratiei 0019.';

comment on column public.dispozitive_conectate.amprenta is
  'Cheia stabila a dispozitivului: iesirea lui descrieDispozitiv() din frontend/src/lib/dispozitive.ts, forma "browser|sistem|desktop". Nu contine versiuni, deci nu se schimba la update de browser.';

comment on column public.dispozitive_conectate.eticheta is
  'Textul aratat omului ("Chrome pe Windows"). Denormalizat intentionat: parserul se poate schimba, dar randurile vechi trebuie sa ramana citibile.';

comment on column public.dispozitive_conectate.agent_utilizator is
  'User-Agent brut, pastrat pentru diagnostic cand eticheta iese "Dispozitiv necunoscut". Nu se afiseaza.';

comment on column public.dispozitive_conectate.id_sesiune is
  'Claim-ul session_id din JWT-ul sesiunii curente de pe acest dispozitiv. NU e cheie: se rescrie la fiecare login. Serveste la marcarea randului "acest dispozitiv" si la pastrarea lui cand se deconecteaza celelalte.';

comment on column public.dispozitive_conectate.creat_la is
  'Primul login de pe acest dispozitiv. Upsert-ul nu il trimite, deci supravietuieste re-logarilor.';

comment on column public.dispozitive_conectate.ultima_activitate is
  'Ultimul login SAU ultima deschidere a paginii de setari — NU "ultima cerere". De aceea interfata scrie "Conectat la ...", niciodata "Activ acum": nu avem datele pentru a doua varianta.';

-- Citirea e mereu "dispozitivele mele, cele mai recente primele".
create index if not exists dispozitive_conectate_id_user_idx
  on public.dispozitive_conectate (id_user, ultima_activitate desc);


-- -----------------------------------------------------------------------------
-- 3. RLS — omul isi citeste randurile, scrie doar service_role
--
-- Aceeasi impartire ca la identity_verifications (0007): aplicatia scrie prin
-- createAdminClient(), deci nu exista politica de insert/update/delete pentru
-- 'authenticated'. Un client care ar putea scrie aici si-ar putea inventa
-- dispozitive sau si-ar putea sterge urmele — exact ce nu vrem pe un ecran de
-- securitate.
-- -----------------------------------------------------------------------------
alter table public.dispozitive_conectate enable row level security;

drop policy if exists "dispozitive proprii: select" on public.dispozitive_conectate;
create policy "dispozitive proprii: select"
  on public.dispozitive_conectate
  for select
  to authenticated
  using ((select auth.uid()) = id_user);

grant select on public.dispozitive_conectate to authenticated;

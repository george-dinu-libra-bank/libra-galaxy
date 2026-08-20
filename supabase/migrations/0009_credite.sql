-- =============================================================================
-- Libra — creditarea (Galaxy Flex Personal)
--
-- Pana acum banca putea vorbi despre credite (corpusul din galaxy-bank-knowledge
-- e indexat si asistentul il citeaza), dar nu putea da unul. Migrarea asta aduce
-- tot ciclul de viata: cerere -> verificari -> decizie -> oferta -> semnare ->
-- disbursement -> grafic -> rate -> rambursare anticipata -> inchidere.
--
-- Valorile produsului nu sunt inventate aici: vin din
-- galaxy-bank-knowledge/credite/credit-nevoi-personale.md si eligibilitate.md
-- (9,90% fix, 21-70 ani, venit net minim 3.000 RON, 6 luni la angajator, 12 luni
-- de venituri). Daca documentul se schimba, se schimba randul din credit_produse.
--
-- Doua observatii despre starea reala a bazei, constatate inainte de a scrie:
--
--   1. `supabase_migrations` e gol — schema existenta a fost construita direct in
--      SQL Editor, nu prin migratii. Fisierele din supabase/migrations/ sunt
--      documentatie a intentiei, nu istoricul aplicat.
--   2. `profiles.rol` si `public.este_administrator()` din 0008 NU exista in baza.
--      Rolurile traiesc in `public.user_roles(user_id, role)`. Consolidam pe
--      acela (REGULI.md #2: o singura implementare per responsabilitate) si
--      definim aici `este_administrator()` peste el, fiindca politicile de mai
--      jos au nevoie de functie, nu de un subselect repetat de opt ori.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 0. Cine e administrator
--
-- SECURITY DEFINER pentru acelasi motiv ca in restul bazei: o politica pe o
-- tabela care ar citi tot din tabela protejata ar reintra in RLS. Functia
-- ruleaza cu drepturile proprietarului si rupe bucla.
-- -----------------------------------------------------------------------------
create or replace function public.este_administrator()
returns boolean
language sql
stable
security definer
set search_path to ''
as $$
  select exists (
    select 1
      from public.user_roles r
     where r.user_id = auth.uid()
       and r.role = 'administrator'
  );
$$;

comment on function public.este_administrator() is
  'True daca utilizatorul din sesiune are rol de administrator in public.user_roles.';


-- -----------------------------------------------------------------------------
-- 1. Catalogul de produse
--
-- Produsul e un rand, nu constante in cod: al doilea produs (Galaxy Mortgage,
-- card de credit) devine un INSERT, nu un refactor.
-- -----------------------------------------------------------------------------
create table if not exists public.credit_produse (
  id                     uuid primary key default gen_random_uuid(),
  slug                   text        not null unique,
  nume                   text        not null,
  dobanda_anuala         numeric(6,4) not null,
  suma_min               numeric(14,2) not null,
  suma_max               numeric(14,2) not null,
  luni_min               integer     not null,
  luni_max               integer     not null,
  varsta_min             integer     not null,
  varsta_max             integer     not null,
  venit_net_minim        numeric(14,2) not null,
  vechime_angajator_luni integer     not null,
  vechime_venituri_luni  integer     not null,
  activ                  boolean     not null default true,
  creat_la               timestamptz not null default now(),

  constraint credit_produse_dobanda_check  check (dobanda_anuala >= 0 and dobanda_anuala < 1),
  constraint credit_produse_suma_check     check (suma_min > 0 and suma_max >= suma_min),
  constraint credit_produse_luni_check     check (luni_min >= 1 and luni_max >= luni_min),
  constraint credit_produse_varsta_check   check (varsta_min >= 18 and varsta_max > varsta_min)
);

comment on table public.credit_produse is
  'Catalogul de produse de creditare. Valorile vin din galaxy-bank-knowledge/credite/.';
comment on column public.credit_produse.dobanda_anuala is
  'Fractie, nu procent: 0.0990 inseamna 9,90% pe an.';

insert into public.credit_produse (
  slug, nume, dobanda_anuala, suma_min, suma_max, luni_min, luni_max,
  varsta_min, varsta_max, venit_net_minim, vechime_angajator_luni, vechime_venituri_luni
)
values (
  'galaxy-flex-personal', 'Galaxy Flex Personal', 0.0990, 5000.00, 150000.00, 6, 60,
  21, 70, 3000.00, 6, 12
)
on conflict (slug) do nothing;


-- -----------------------------------------------------------------------------
-- 2. Cererea de credit
-- -----------------------------------------------------------------------------
create table if not exists public.credit_cereri (
  id                     uuid primary key default gen_random_uuid(),
  id_user                uuid        not null references public.profiles (id) on delete cascade,
  id_produs              uuid        not null references public.credit_produse (id),

  suma_ceruta            numeric(14,2) not null,
  luni                   integer     not null,
  scop                   text,

  -- Ce declara clientul. Se pastreaza chiar daca verificarile il contrazic:
  -- diferenta dintre declarat si constatat e ea insasi un semnal de risc.
  venit_declarat         numeric(14,2),
  angajator              text,
  vechime_angajator_luni integer,
  obligatii_declarate    numeric(14,2) not null default 0,

  -- Rezultatul analizei.
  venit_folosit          numeric(14,2),
  obligatii_folosite     numeric(14,2),
  dti                    numeric(6,4),
  scor                   integer,
  motive                 jsonb       not null default '[]'::jsonb,
  explicatie             text,

  -- Oferta, completata cand decizia e favorabila.
  rata_lunara            numeric(14,2),
  dae                    numeric(6,4),
  oferta_expira_la       timestamptz,

  status                 text        not null default 'ciorna',
  creat_la               timestamptz not null default now(),
  modificat_la           timestamptz not null default now(),

  constraint credit_cereri_suma_check   check (suma_ceruta > 0),
  constraint credit_cereri_luni_check   check (luni >= 1),
  constraint credit_cereri_scor_check   check (scor is null or scor between 0 and 100),
  constraint credit_cereri_status_check check (status in (
    'ciorna', 'in_analiza', 'oferta', 'analiza_manuala',
    'respinsa', 'acceptata', 'anulata', 'expirata'
  ))
);

comment on table public.credit_cereri is
  'O cerere de credit, de la ciorna pana la acceptare sau respingere.';
comment on column public.credit_cereri.motive is
  'Lista structurata de {cod, text} — motivele deciziei. Explicatia in limbaj natural se genereaza din ele, nu invers.';
comment on column public.credit_cereri.dti is
  'Gradul de indatorare: (obligatii + rata noua) / venit net. Pragul aplicat e 0.40.';

create index if not exists credit_cereri_user_idx on public.credit_cereri (id_user, creat_la desc);
create index if not exists credit_cereri_status_idx on public.credit_cereri (status) where status = 'analiza_manuala';


-- -----------------------------------------------------------------------------
-- 3. Verificarile de venit — cum a ajuns banca la cifra
--
-- Neavand ANAF sau Biroul de Credit, se coroboreaza patru surse. Fiecare lasa
-- un rand aici, deci decizia e reconstituibila peste sase luni.
-- -----------------------------------------------------------------------------
create table if not exists public.credit_verificari_venit (
  id                    uuid primary key default gen_random_uuid(),
  id_cerere             uuid        not null references public.credit_cereri (id) on delete cascade,
  sursa                 text        not null,
  venit_constatat       numeric(14,2),
  obligatii_constatate  numeric(14,2),
  incredere             numeric(4,3),
  detalii               jsonb       not null default '{}'::jsonb,
  creat_la              timestamptz not null default now(),

  constraint credit_verificari_sursa_check check (sursa in (
    'tranzactii', 'adeverinta', 'declarat', 'birou_credit'
  )),
  constraint credit_verificari_incredere_check check (incredere is null or incredere between 0 and 1)
);

comment on column public.credit_verificari_venit.sursa is
  'tranzactii = dedus din incasarile recurente reale; adeverinta = extras din document; declarat = spus de client; birou_credit = registrul intern de expuneri.';

create index if not exists credit_verificari_cerere_idx on public.credit_verificari_venit (id_cerere);


-- -----------------------------------------------------------------------------
-- 4. Documentele cererii
-- -----------------------------------------------------------------------------
create table if not exists public.credit_documente (
  id            uuid primary key default gen_random_uuid(),
  id_cerere     uuid        not null references public.credit_cereri (id) on delete cascade,
  id_user       uuid        not null references public.profiles (id) on delete cascade,
  tip           text        not null,
  storage_path  text        not null,
  content_type  text,
  marime_octeti integer,
  extras        jsonb       not null default '{}'::jsonb,
  status        text        not null default 'incarcat',
  creat_la      timestamptz not null default now(),

  constraint credit_documente_tip_check    check (tip in ('adeverinta_venit', 'contract')),
  constraint credit_documente_status_check check (status in ('incarcat', 'procesat', 'ilizibil')),
  constraint credit_documente_marime_check check (marime_octeti is null or marime_octeti > 0)
);

create index if not exists credit_documente_cerere_idx on public.credit_documente (id_cerere);


-- -----------------------------------------------------------------------------
-- 5. Creditul acordat (contractul)
-- -----------------------------------------------------------------------------
create table if not exists public.credite (
  id                uuid primary key default gen_random_uuid(),
  id_cerere         uuid        not null unique references public.credit_cereri (id),
  id_user           uuid        not null references public.profiles (id) on delete cascade,
  id_cont_creditare uuid        not null references public.conturi_bancare (id),

  principal         numeric(14,2) not null,
  dobanda_anuala    numeric(6,4) not null,
  luni              integer     not null,
  rata_lunara       numeric(14,2) not null,
  dae               numeric(6,4),
  sold_ramas        numeric(14,2) not null,

  data_acordarii    date        not null default current_date,
  semnat_la         timestamptz not null default now(),
  -- IP, user agent si momentul semnarii. Nu e semnatura calificata, dar e o
  -- urma verificabila a consimtamantului, ceea ce un buton simplu nu e.
  semnatura         jsonb       not null default '{}'::jsonb,

  status            text        not null default 'activ',
  inchis_la         timestamptz,
  creat_la          timestamptz not null default now(),
  modificat_la      timestamptz not null default now(),

  constraint credite_principal_check check (principal > 0),
  constraint credite_sold_check      check (sold_ramas >= 0 and sold_ramas <= principal),
  constraint credite_luni_check      check (luni >= 1),
  constraint credite_status_check    check (status in ('activ', 'restant', 'inchis', 'rambursat_anticipat'))
);

comment on column public.credite.id_cont_creditare is
  'Contul in care s-au virat banii si din care se incaseaza ratele.';
comment on column public.credite.semnatura is
  'Urma consimtamantului: ip, user_agent, moment. Nu e semnatura electronica calificata.';

create index if not exists credite_user_idx on public.credite (id_user, creat_la desc);
create index if not exists credite_active_idx on public.credite (status) where status in ('activ', 'restant');


-- -----------------------------------------------------------------------------
-- 6. Graficul de rambursare
--
-- Unique-ul (id_credit, numar_rata) e ce face procesarea ratelor idempotenta:
-- doua apeluri concurente nu pot incasa aceeasi rata de doua ori.
-- -----------------------------------------------------------------------------
create table if not exists public.credit_rate (
  id             uuid primary key default gen_random_uuid(),
  id_credit      uuid        not null references public.credite (id) on delete cascade,
  numar_rata     integer     not null,
  scadenta       date        not null,
  principal_rata numeric(14,2) not null,
  dobanda_rata   numeric(14,2) not null,
  rata_totala    numeric(14,2) not null,
  sold_dupa      numeric(14,2) not null,
  status         text        not null default 'programata',
  platita_la     timestamptz,
  id_tranzactie  uuid        references public.tranzactii (id) on delete set null,

  constraint credit_rate_numar_check  check (numar_rata >= 1),
  constraint credit_rate_sume_check   check (principal_rata >= 0 and dobanda_rata >= 0 and rata_totala > 0),
  constraint credit_rate_sold_check   check (sold_dupa >= 0),
  constraint credit_rate_status_check check (status in ('programata', 'platita', 'restanta', 'anulata')),
  constraint credit_rate_unica unique (id_credit, numar_rata)
);

create index if not exists credit_rate_scadente_idx
  on public.credit_rate (scadenta) where status = 'programata';


-- -----------------------------------------------------------------------------
-- 7. Registrul intern de expuneri — tine locul Biroului de Credit
--
-- Fara acces la Biroul de Credit real, gradul de indatorare s-ar calcula doar pe
-- ce declara clientul. Tabela asta e populata din seed si consultata la scoring,
-- ca DTI-ul sa fie verificat, nu crezut pe cuvant.
--
-- Nicio politica RLS pentru 'authenticated': un client nu are ce cauta in
-- expunerile nimanui, nici macar in ale lui, prin API-ul public.
-- -----------------------------------------------------------------------------
create table if not exists public.credit_bureau_simulat (
  id          uuid primary key default gen_random_uuid(),
  cnp         text        not null,
  banca       text        not null,
  tip_produs  text        not null,
  rata_lunara numeric(14,2) not null,
  sold        numeric(14,2) not null default 0,
  activ       boolean     not null default true,
  creat_la    timestamptz not null default now(),

  constraint credit_bureau_cnp_check  check (cnp ~ '^[1-8][0-9]{12}$'),
  constraint credit_bureau_rata_check check (rata_lunara >= 0)
);

comment on table public.credit_bureau_simulat is
  'Substitut pentru Biroul de Credit. Doar service_role — niciun client nu il citeste direct.';

create index if not exists credit_bureau_cnp_idx
  on public.credit_bureau_simulat (cnp) where activ;


-- -----------------------------------------------------------------------------
-- 8. Audit trail
-- -----------------------------------------------------------------------------
create table if not exists public.credit_evenimente (
  id        uuid primary key default gen_random_uuid(),
  id_cerere uuid        references public.credit_cereri (id) on delete cascade,
  id_credit uuid        references public.credite (id) on delete cascade,
  tip       text        not null,
  actor     text        not null default 'sistem',
  id_actor  uuid        references public.profiles (id) on delete set null,
  detalii   jsonb       not null default '{}'::jsonb,
  creat_la  timestamptz not null default now(),

  constraint credit_evenimente_actor_check check (actor in ('client', 'sistem', 'administrator')),
  constraint credit_evenimente_tinta_check check (id_cerere is not null or id_credit is not null)
);

comment on table public.credit_evenimente is
  'Urma fiecarei tranzitii de stare. Un credit fara audit trail nu se poate contesta si nici apara.';

create index if not exists credit_evenimente_cerere_idx on public.credit_evenimente (id_cerere, creat_la desc);
create index if not exists credit_evenimente_credit_idx on public.credit_evenimente (id_credit, creat_la desc);


-- -----------------------------------------------------------------------------
-- 9. modificat_la, ca in restul bazei
-- -----------------------------------------------------------------------------
create or replace function public.credit_modificat_la()
returns trigger
language plpgsql
set search_path to ''
as $$
begin
  new.modificat_la := now();
  return new;
end;
$$;

drop trigger if exists credit_cereri_modificat_la on public.credit_cereri;
create trigger credit_cereri_modificat_la
  before update on public.credit_cereri
  for each row execute function public.credit_modificat_la();

drop trigger if exists credite_modificat_la on public.credite;
create trigger credite_modificat_la
  before update on public.credite
  for each row execute function public.credit_modificat_la();


-- -----------------------------------------------------------------------------
-- 10. RLS
--
-- Acelasi tipar ca la carduri, tranzactii si identity_verifications: clientul
-- CITESTE ce e al lui, dar nu scrie nimic direct. Toate mutatiile trec prin
-- FastAPI cu service_role, ca sa nu poata cineva sa-si insereze un credit
-- aprobat sau sa-si marcheze o rata ca platita.
-- -----------------------------------------------------------------------------
alter table public.credit_produse         enable row level security;
alter table public.credit_cereri          enable row level security;
alter table public.credit_verificari_venit enable row level security;
alter table public.credit_documente       enable row level security;
alter table public.credite                enable row level security;
alter table public.credit_rate            enable row level security;
alter table public.credit_bureau_simulat  enable row level security;
alter table public.credit_evenimente      enable row level security;

-- Catalogul e public pentru orice utilizator autentificat: simulatorul are
-- nevoie de dobanda si de limite ca sa calculeze o rata.
drop policy if exists "produse active: select" on public.credit_produse;
create policy "produse active: select"
  on public.credit_produse for select to authenticated
  using (activ);

drop policy if exists "cereri proprii: select" on public.credit_cereri;
create policy "cereri proprii: select"
  on public.credit_cereri for select to authenticated
  using (auth.uid() = id_user or public.este_administrator());

drop policy if exists "verificari proprii: select" on public.credit_verificari_venit;
create policy "verificari proprii: select"
  on public.credit_verificari_venit for select to authenticated
  using (
    public.este_administrator()
    or exists (
      select 1 from public.credit_cereri c
       where c.id = credit_verificari_venit.id_cerere and c.id_user = auth.uid()
    )
  );

drop policy if exists "documente proprii: select" on public.credit_documente;
create policy "documente proprii: select"
  on public.credit_documente for select to authenticated
  using (auth.uid() = id_user or public.este_administrator());

drop policy if exists "credite proprii: select" on public.credite;
create policy "credite proprii: select"
  on public.credite for select to authenticated
  using (auth.uid() = id_user or public.este_administrator());

drop policy if exists "rate proprii: select" on public.credit_rate;
create policy "rate proprii: select"
  on public.credit_rate for select to authenticated
  using (
    public.este_administrator()
    or exists (
      select 1 from public.credite c
       where c.id = credit_rate.id_credit and c.id_user = auth.uid()
    )
  );

drop policy if exists "evenimente proprii: select" on public.credit_evenimente;
create policy "evenimente proprii: select"
  on public.credit_evenimente for select to authenticated
  using (
    public.este_administrator()
    or exists (select 1 from public.credit_cereri c where c.id = credit_evenimente.id_cerere and c.id_user = auth.uid())
    or exists (select 1 from public.credite  k where k.id = credit_evenimente.id_credit and k.id_user = auth.uid())
  );

-- credit_bureau_simulat ramane fara nicio politica: RLS activ + zero politici
-- inseamna ca niciun rol 'authenticated' nu vede niciun rand. service_role
-- ocoleste RLS, deci backendul citeste normal.

grant select on public.credit_produse          to authenticated;
grant select on public.credit_cereri           to authenticated;
grant select on public.credit_verificari_venit to authenticated;
grant select on public.credit_documente        to authenticated;
grant select on public.credite                 to authenticated;
grant select on public.credit_rate             to authenticated;
grant select on public.credit_evenimente       to authenticated;


-- -----------------------------------------------------------------------------
-- 11. Storage: bucket privat pentru adeverinte si contracte
--
-- Ca la 'buletine' si 'selfie-uri': privat, si fiecare om doar in folderul lui.
-- Incarcarea reala se face din backend cu service_role; politicile raman plasa
-- de siguranta pentru orice acces facut cu sesiunea utilizatorului.
-- -----------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('credit-documente', 'credit-documente', false)
on conflict (id) do nothing;

drop policy if exists "credit-documente: user isi incarca documentul" on storage.objects;
create policy "credit-documente: user isi incarca documentul"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'credit-documente' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "credit-documente: user isi vede documentul" on storage.objects;
create policy "credit-documente: user isi vede documentul"
  on storage.objects for select to authenticated
  using (bucket_id = 'credit-documente' and (storage.foldername(name))[1] = auth.uid()::text);


-- -----------------------------------------------------------------------------
-- 12. Restrangerea lui este_administrator()
--
-- Adaugata dupa aplicare, la semnalarea database linter-ului (regula 0028):
-- functia era expusa ca RPC public, /rest/v1/rpc/este_administrator, pentru
-- rolul anon.
--
-- 'authenticated' PASTREAZA execute, si nu e o scapare: politicile RLS de mai
-- sus o apeleaza in contextul rolului care interogheaza, deci un revoke pe el ar
-- transforma orice select pe credit_* intr-un permission denied.
-- -----------------------------------------------------------------------------
revoke execute on function public.este_administrator() from public;
revoke execute on function public.este_administrator() from anon;
grant execute on function public.este_administrator() to authenticated;
grant execute on function public.este_administrator() to service_role;

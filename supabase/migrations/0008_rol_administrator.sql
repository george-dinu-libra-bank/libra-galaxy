-- =============================================================================
-- Libra — rolul de administrator si urma pe care o lasa
--
-- Pana acum fiecare utilizator vedea exact un rand: al lui. Detectia de
-- neregularitati are insa nevoie de cineva care sa se uite peste ele, altfel
-- semnalarile raman intr-un cont in care nimeni nu intra.
--
-- Doua lucruri merg impreuna aici, si nu se despart:
--   1. dreptul de a citi datele altcuiva;
--   2. urma ca l-ai folosit (public.acces_administrator).
-- Un drept de citire fara urma nu se poate verifica ulterior, iar aici vorbim
-- de istoricul financiar al unor oameni.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Rolul
-- -----------------------------------------------------------------------------
alter table public.profiles
  add column if not exists rol text not null default 'client';

alter table public.profiles drop constraint if exists profiles_rol_check;
alter table public.profiles
  add constraint profiles_rol_check check (rol in ('client', 'administrator'));

comment on column public.profiles.rol is
  'client sau administrator. Se schimba numai din consola Supabase, niciodata din aplicatie.';

-- Rolul nu se schimba din aplicatie: trigger-ul de la 0001 il ingheata, ca pe
-- CNP si IBAN. Altfel oricine si-ar putea acorda singur drepturi cu un update
-- pe propriul profil, care ii este permis de RLS.
create or replace function public.profiles_protejeaza_campuri()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.id        := old.id;
  new.cnp       := old.cnp;
  new.iban_cont := old.iban_cont;
  new.creat_la  := old.creat_la;
  new.rol       := old.rol;
  new.modificat_la := now();

  return new;
end;
$$;

-- -----------------------------------------------------------------------------
-- 2. Cine e administrator
--
-- SECURITY DEFINER, si nu un subselect direct in politica: o politica pe
-- profiles care ar citi tot din profiles ar declansa din nou RLS pe aceeasi
-- tabela, la infinit. Functia ruleaza cu drepturile proprietarului, deci vede
-- randul fara sa mai treaca prin politici, si bucla se rupe.
-- -----------------------------------------------------------------------------
create or replace function public.este_administrator()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.profiles p
    where p.id = (select auth.uid()) and p.rol = 'administrator'
  );
$$;

revoke all on function public.este_administrator() from public;
grant execute on function public.este_administrator() to authenticated;

-- -----------------------------------------------------------------------------
-- 3. Ce vede un administrator
--
-- Politicile de citire proprii raman neatinse; se adauga cate una separata
-- pentru administratori, ca sa se vada in baza de date ca sunt doua drepturi
-- diferite, nu unul largit.
-- -----------------------------------------------------------------------------
drop policy if exists "administrator: vede toate profilurile" on public.profiles;
create policy "administrator: vede toate profilurile"
  on public.profiles
  for select
  to authenticated
  using (public.este_administrator());

drop policy if exists "administrator: vede toate tranzactiile" on public.tranzactii;
create policy "administrator: vede toate tranzactiile"
  on public.tranzactii
  for select
  to authenticated
  using (public.este_administrator());

drop policy if exists "administrator: vede toate cardurile" on public.carduri;
create policy "administrator: vede toate cardurile"
  on public.carduri
  for select
  to authenticated
  using (public.este_administrator());

-- Numai citire: un administrator se uita, nu modifica. Blocarea unui card sau
-- oprirea unui transfer sunt actiuni cu urmari, si isi cer propriul flux, cu
-- confirmare — nu vin pe usa din dos a unei politici de select.

-- -----------------------------------------------------------------------------
-- 4. Urma
-- -----------------------------------------------------------------------------
create table if not exists public.acces_administrator (
  id                uuid primary key default gen_random_uuid(),
  id_administrator  uuid not null references public.profiles (id) on delete cascade,
  id_utilizator     uuid references public.profiles (id) on delete set null,
  actiune           text not null,
  detalii           text,
  creat_la          timestamptz not null default now(),

  constraint acces_actiune_check check (actiune in ('lista_alerte', 'raport_pdf', 'raport_csv'))
);

comment on table public.acces_administrator is
  'Cine s-a uitat la datele cui, si cand. Se adauga, nu se modifica si nu se sterge.';

create index if not exists acces_administrator_idx
  on public.acces_administrator (id_administrator, creat_la desc);
create index if not exists acces_utilizator_idx
  on public.acces_administrator (id_utilizator, creat_la desc);

alter table public.acces_administrator enable row level security;

-- Un administrator isi vede propria urma. Nu si pe a colegilor: cine verifica
-- verificatorii se uita in baza de date cu service_role, nu prin aplicatie.
drop policy if exists "administrator: isi vede urma" on public.acces_administrator;
create policy "administrator: isi vede urma"
  on public.acces_administrator
  for select
  to authenticated
  using (id_administrator = (select auth.uid()) and public.este_administrator());

-- Se poate scrie doar in nume propriu. Fara update si fara delete: o urma care
-- se poate rescrie nu mai e o urma.
drop policy if exists "administrator: isi scrie urma" on public.acces_administrator;
create policy "administrator: isi scrie urma"
  on public.acces_administrator
  for insert
  to authenticated
  with check (id_administrator = (select auth.uid()) and public.este_administrator());

grant select, insert on public.acces_administrator to authenticated;

-- -----------------------------------------------------------------------------
-- 5. Cum faci primul administrator
--
-- Din SQL Editor-ul Supabase, cu service_role (deci peste trigger-ul care
-- ingheata rolul):
--
--   update public.profiles set rol = 'administrator'
--    where email = 'adresa@exemplu.ro';
--
-- Trigger-ul de la punctul 1 ruleaza si aici, deci update-ul simplu nu trece.
-- Se face cu trigger-ul oprit pentru o clipa:
--
--   alter table public.profiles disable trigger profiles_before_update;
--   update public.profiles set rol = 'administrator' where email = '...';
--   alter table public.profiles enable trigger profiles_before_update;
-- -----------------------------------------------------------------------------

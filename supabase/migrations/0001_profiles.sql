-- =============================================================================
-- Libra — profiluri de utilizator create automat la inregistrare
--
-- La INSERT in auth.users, un trigger copiaza datele din raw_user_meta_data
-- (nume, cnp, telefon, iban_cont) impreuna cu email-ul din auth.users
-- intr-un rand nou din public.profiles.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Tabela de profiluri
-- -----------------------------------------------------------------------------
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  nume        text        not null,
  cnp         text        not null unique,
  telefon     text        not null,
  email       text        not null unique,
  iban_cont   text        not null unique,
  creat_la    timestamptz not null default now(),
  modificat_la timestamptz not null default now(),

  constraint profiles_nume_check    check (char_length(btrim(nume)) between 3 and 120),
  constraint profiles_cnp_check     check (cnp ~ '^[1-8][0-9]{12}$'),
  constraint profiles_telefon_check check (telefon ~ '^\+40[0-9]{9}$'),
  constraint profiles_email_check   check (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  constraint profiles_iban_check    check (iban_cont ~ '^RO[0-9]{2}[A-Z0-9]{20}$')
);

comment on table  public.profiles is 'Date de client, populate automat de trigger-ul de pe auth.users.';
comment on column public.profiles.cnp       is 'Cod numeric personal, 13 cifre. Nu se afiseaza integral in UI.';
comment on column public.profiles.iban_cont is 'IBAN-ul contului curent, generat la inregistrare.';

create index if not exists profiles_email_idx on public.profiles (email);

-- -----------------------------------------------------------------------------
-- 2. Generator de IBAN (folosit ca fallback daca metadata nu contine unul)
-- -----------------------------------------------------------------------------

-- Restul impartirii la 97 pentru un sir lung de cifre, calculat pe bucati
-- ca sa nu depasim intervalul numeric.
create or replace function public.iban_mod97(p_digits text)
returns integer
language plpgsql
immutable
set search_path = ''
as $$
declare
  v_rest text := '';
  v_bucata text;
  i integer := 1;
begin
  while i <= char_length(p_digits) loop
    v_bucata := v_rest || substr(p_digits, i, 7);
    v_rest   := (v_bucata::bigint % 97)::text;
    i := i + 7;
  end loop;

  return v_rest::integer;
end;
$$;

-- Transforma literele in cifre (A=10 ... Z=35), conform ISO 13616.
create or replace function public.iban_litere_in_cifre(p_text text)
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  v_out text := '';
  v_ch  text;
  i integer;
begin
  for i in 1..char_length(p_text) loop
    v_ch := substr(upper(p_text), i, 1);
    if v_ch ~ '[0-9]' then
      v_out := v_out || v_ch;
    elsif v_ch ~ '[A-Z]' then
      v_out := v_out || (ascii(v_ch) - 55)::text;
    else
      raise exception 'Caracter invalid in IBAN: %', v_ch;
    end if;
  end loop;

  return v_out;
end;
$$;

-- Genereaza un IBAN romanesc valid: RO + cifre de control + LIBR + 16 cifre.
create or replace function public.genereaza_iban()
returns text
language plpgsql
volatile
set search_path = ''
as $$
declare
  v_banca text := 'LIBR';
  v_cont  text;
  v_control integer;
  i integer;
begin
  for i in 1..40 loop
    v_cont := lpad(floor(random() * 1e16)::bigint::text, 16, '0');

    -- Cifrele de control: 98 - mod97(BBAN || "RO00" rearanjat)
    v_control := 98 - public.iban_mod97(
      public.iban_litere_in_cifre(v_banca || v_cont || 'RO00')
    );

    v_cont := 'RO' || lpad(v_control::text, 2, '0') || v_banca || v_cont;

    if not exists (select 1 from public.profiles p where p.iban_cont = v_cont) then
      return v_cont;
    end if;
  end loop;

  raise exception 'Nu s-a putut genera un IBAN unic.';
end;
$$;

-- -----------------------------------------------------------------------------
-- 3. Trigger: auth.users -> public.profiles
-- -----------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_meta      jsonb := coalesce(new.raw_user_meta_data, '{}'::jsonb);
  v_nume      text  := nullif(btrim(v_meta ->> 'nume'), '');
  v_cnp       text  := nullif(btrim(v_meta ->> 'cnp'), '');
  v_telefon   text  := nullif(btrim(v_meta ->> 'telefon'), '');
  v_iban      text  := nullif(btrim(upper(v_meta ->> 'iban_cont')), '');
begin
  if v_nume is null then
    raise exception 'Lipseste "nume" din user_metadata.' using errcode = '23514';
  end if;

  if v_cnp is null then
    raise exception 'Lipseste "cnp" din user_metadata.' using errcode = '23514';
  end if;

  if v_telefon is null then
    raise exception 'Lipseste "telefon" din user_metadata.' using errcode = '23514';
  end if;

  -- Normalizare telefon: 07xx xxx xxx -> +407xxxxxxxx
  v_telefon := regexp_replace(v_telefon, '[^0-9+]', '', 'g');
  if v_telefon ~ '^0[0-9]{9}$' then
    v_telefon := '+4' || v_telefon;
  elsif v_telefon ~ '^40[0-9]{9}$' then
    v_telefon := '+' || v_telefon;
  end if;

  -- IBAN-ul vine din metadata; daca lipseste, il generam aici.
  if v_iban is null then
    v_iban := public.genereaza_iban();
  end if;

  insert into public.profiles (id, nume, cnp, telefon, email, iban_cont)
  values (new.id, v_nume, v_cnp, v_telefon, new.email, v_iban);

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

-- Tine email-ul din profil sincronizat daca utilizatorul si-l schimba.
create or replace function public.handle_user_email_update()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.email is distinct from old.email then
    update public.profiles
       set email = new.email,
           modificat_la = now()
     where id = new.id;
  end if;

  return new;
end;
$$;

drop trigger if exists on_auth_user_email_updated on auth.users;

create trigger on_auth_user_email_updated
  after update of email on auth.users
  for each row
  execute function public.handle_user_email_update();

-- -----------------------------------------------------------------------------
-- 4. Campuri imutabile + timestamp
-- -----------------------------------------------------------------------------
create or replace function public.profiles_protejeaza_campuri()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  -- CNP-ul, IBAN-ul si id-ul nu se schimba din aplicatie.
  new.id        := old.id;
  new.cnp       := old.cnp;
  new.iban_cont := old.iban_cont;
  new.creat_la  := old.creat_la;
  new.modificat_la := now();

  return new;
end;
$$;

drop trigger if exists profiles_before_update on public.profiles;

create trigger profiles_before_update
  before update on public.profiles
  for each row
  execute function public.profiles_protejeaza_campuri();

-- -----------------------------------------------------------------------------
-- 5. RLS — fiecare utilizator vede si isi editeaza doar propriul profil
-- -----------------------------------------------------------------------------
alter table public.profiles enable row level security;

drop policy if exists "profil propriu: select" on public.profiles;
create policy "profil propriu: select"
  on public.profiles
  for select
  to authenticated
  using (auth.uid() = id);

drop policy if exists "profil propriu: update" on public.profiles;
create policy "profil propriu: update"
  on public.profiles
  for update
  to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Nu exista politici de INSERT/DELETE: randurile apar si dispar exclusiv
-- prin trigger-ul de pe auth.users.

grant select, update on public.profiles to authenticated;

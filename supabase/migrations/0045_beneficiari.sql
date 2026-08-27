-- =============================================================================
-- 0045 — beneficiari reali, persistenti, legati de IBAN
--
-- Pana acum "beneficiarii" erau doar date simulate (frontend/src/lib/mock-data.ts):
-- {nume, iban, banca}, nimic salvat, nicio legatura cu un cont Galaxy Bank real.
-- Asta ii facea nefolositori pentru invitatul in grup (0044_invitatii_grup.sql
-- are nevoie de un uuid de profil real).
--
-- Aici beneficiarii devin o tabela reala, proprie fiecarui utilizator, iar la
-- adaugare IBAN-ul e verificat contra public.conturi_bancare: daca apartine
-- unui cont Galaxy Bank, beneficiarul retine `id_user_legat` (proprietarul
-- acelui cont) — acela e singurul caz in care poate fi invitat intr-un grup.
-- Un beneficiar extern (IBAN de la alta banca) ramane in lista, dar fara
-- legatura, exact ca inainte.
-- =============================================================================

create table if not exists public.beneficiari (
  id            uuid        primary key default gen_random_uuid(),
  id_user       uuid        not null references public.profiles (id) on delete cascade,
  nume          text        not null,
  iban          text        not null,
  banca         text        not null default 'Cont extern',
  favorit       boolean     not null default false,
  -- Proprietarul contului Galaxy Bank cu acest IBAN, daca exista. Null pentru
  -- un beneficiar extern (alta banca) — nu poate fi invitat intr-un grup.
  id_user_legat uuid        references public.profiles (id) on delete set null,
  creat_la      timestamptz not null default now(),
  modificat_la  timestamptz not null default now(),

  constraint beneficiari_nume_check check (char_length(nume) between 2 and 60),
  constraint beneficiari_iban_check check (iban ~ '^RO[0-9]{2}[A-Z0-9]{20}$')
);

comment on table public.beneficiari is
  'Beneficiari salvati de fiecare utilizator. id_user_legat se completeaza automat la insert, prin potrivire de IBAN cu conturi_bancare — vezi beneficiari_before_insert().';

create unique index if not exists beneficiari_user_iban_unic on public.beneficiari (id_user, iban);
create index if not exists beneficiari_id_user_idx on public.beneficiari (id_user);

-- -----------------------------------------------------------------------------
-- Insert: normalizeaza nume/IBAN si rezolva id_user_legat prin cautare in
-- conturi_bancare. SECURITY DEFINER e necesar strict pentru aceasta cautare —
-- politica de pe conturi_bancare lasa pe fiecare sa-si vada doar conturile
-- proprii, deci fara asta nici n-ar gasi contul altcuiva dupa IBAN.
-- -----------------------------------------------------------------------------
create or replace function public.beneficiari_before_insert()
returns trigger
language plpgsql
security definer
set search_path to ''
as $$
declare
  v_cont public.conturi_bancare%rowtype;
begin
  new.nume := btrim(new.nume);

  if char_length(new.nume) < 2 or char_length(new.nume) > 60 then
    raise exception 'NUME_INVALID'
      using detail = 'Numele trebuie sa aiba intre 2 si 60 de caractere.';
  end if;

  new.iban := upper(regexp_replace(coalesce(new.iban, ''), '\s', '', 'g'));

  if new.iban !~ '^RO[0-9]{2}[A-Z0-9]{20}$' then
    raise exception 'IBAN_INVALID'
      using detail = 'IBAN-ul este invalid.';
  end if;

  new.creat_la := now();
  new.modificat_la := now();

  select * into v_cont from public.conturi_bancare c where c.iban = new.iban;

  if found then
    if v_cont.id_user = new.id_user then
      raise exception 'PROPRIUL_CONT'
        using detail = 'Nu te poti adauga singur ca beneficiar.';
    end if;

    new.id_user_legat := v_cont.id_user;
    new.banca := 'Galaxy Bank';
  else
    new.id_user_legat := null;
    new.banca := coalesce(nullif(btrim(new.banca), ''), 'Cont extern');
  end if;

  return new;
end;
$$;

drop trigger if exists beneficiari_inainte_de_insert on public.beneficiari;

create trigger beneficiari_inainte_de_insert
  before insert on public.beneficiari
  for each row
  execute function public.beneficiari_before_insert();

-- -----------------------------------------------------------------------------
-- Update: din aplicatie se pot schimba doar numele si starea de favorit — restul
-- (IBAN-ul, banca, legatura cu contul) raman fixate de la adaugare, altfel un
-- update direct ar putea ocoli potrivirea facuta la insert.
-- -----------------------------------------------------------------------------
create or replace function public.beneficiari_protejeaza_campuri()
returns trigger
language plpgsql
set search_path to ''
as $$
begin
  new.id            := old.id;
  new.id_user       := old.id_user;
  new.iban          := old.iban;
  new.banca         := old.banca;
  new.id_user_legat := old.id_user_legat;
  new.creat_la      := old.creat_la;
  new.modificat_la  := now();

  return new;
end;
$$;

drop trigger if exists beneficiari_inainte_de_update on public.beneficiari;

create trigger beneficiari_inainte_de_update
  before update on public.beneficiari
  for each row
  execute function public.beneficiari_protejeaza_campuri();

-- -----------------------------------------------------------------------------
-- RLS — CRUD simplu, propriu fiecarui utilizator (acelasi tipar ca la
-- public.carduri, 0002_carduri_tranzactii.sql).
-- -----------------------------------------------------------------------------
alter table public.beneficiari enable row level security;

drop policy if exists "beneficiari proprii: select" on public.beneficiari;
create policy "beneficiari proprii: select"
  on public.beneficiari
  for select
  to authenticated
  using (auth.uid() = id_user);

drop policy if exists "beneficiari proprii: insert" on public.beneficiari;
create policy "beneficiari proprii: insert"
  on public.beneficiari
  for insert
  to authenticated
  with check (auth.uid() = id_user);

drop policy if exists "beneficiari proprii: update" on public.beneficiari;
create policy "beneficiari proprii: update"
  on public.beneficiari
  for update
  to authenticated
  using (auth.uid() = id_user)
  with check (auth.uid() = id_user);

drop policy if exists "beneficiari proprii: delete" on public.beneficiari;
create policy "beneficiari proprii: delete"
  on public.beneficiari
  for delete
  to authenticated
  using (auth.uid() = id_user);

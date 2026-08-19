-- =============================================================================
-- Libra — carduri si tranzactii
--
-- Fiecare profil poate avea unul sau mai multe carduri. Numarul de card, CVV-ul
-- si data de expirare sunt generate in baza de date (trigger before insert),
-- nu de client. Soldul si tranzactiile se modifica doar din backend
-- (service_role); clientul are drept de citire si poate doar bloca/debloca.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Generator de numar de card (Luhn)
-- -----------------------------------------------------------------------------

-- Cifra de control Luhn pentru un sir de cifre fara cifra de control.
create or replace function public.luhn_cifra_control(p_digits text)
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  v_suma  integer := 0;
  v_cifra integer;
  v_len   integer := char_length(p_digits);
  i integer;
begin
  for i in 1..v_len loop
    v_cifra := substr(p_digits, v_len - i + 1, 1)::integer;

    -- Se dubleaza fiecare a doua cifra, numarand de la dreapta.
    if i % 2 = 1 then
      v_cifra := v_cifra * 2;
      if v_cifra > 9 then
        v_cifra := v_cifra - 9;
      end if;
    end if;

    v_suma := v_suma + v_cifra;
  end loop;

  return ((10 - (v_suma % 10)) % 10)::text;
end;
$$;

-- Genereaza un numar de card unic, 16 cifre, valid Luhn.
create or replace function public.genereaza_numar_card()
returns text
language plpgsql
volatile
set search_path = ''
as $$
declare
  v_prefix text := '4';   -- BIN de test
  v_corp   text;
  v_card   text;
  i integer;
begin
  for i in 1..40 loop
    v_corp := v_prefix || lpad(floor(random() * 1e14)::bigint::text, 14, '0');
    v_card := v_corp || public.luhn_cifra_control(v_corp);

    if not exists (select 1 from public.carduri c where c.numar_card = v_card) then
      return v_card;
    end if;
  end loop;

  raise exception 'Nu s-a putut genera un numar de card unic.';
end;
$$;

-- -----------------------------------------------------------------------------
-- 2. Tabela de carduri
-- -----------------------------------------------------------------------------
create table if not exists public.carduri (
  id             uuid primary key default gen_random_uuid(),
  id_user        uuid        not null references public.profiles (id) on delete cascade,
  numar_card     text        not null unique,
  data_expirare  text        not null,
  ccv            text        not null,
  sold_curent    numeric(14,2) not null default 0,
  is_blocked     boolean     not null default false,
  creat_la       timestamptz not null default now(),
  modificat_la   timestamptz not null default now(),

  constraint carduri_numar_check    check (numar_card ~ '^[0-9]{16}$'),
  constraint carduri_expirare_check check (data_expirare ~ '^(0[1-9]|1[0-2])/[0-9]{2}$'),
  constraint carduri_ccv_check      check (ccv ~ '^[0-9]{3}$'),
  constraint carduri_sold_check     check (sold_curent >= 0)
);

comment on table  public.carduri is 'Carduri emise pe profilurile din public.profiles.';
comment on column public.carduri.data_expirare is 'Luna/an, format MM/YY (ex. 08/30).';
comment on column public.carduri.ccv         is 'Cod de securitate, 3 cifre. Proiect didactic — intr-un sistem real CVV-ul nu se stocheaza.';
comment on column public.carduri.sold_curent is 'Sold in RON. Se modifica doar din backend (service_role).';

create index if not exists carduri_id_user_idx on public.carduri (id_user);

-- Data de expirare ca data reala (ultima zi a lunii), pentru comparatii.
alter table public.carduri
  drop column if exists expira_la;

alter table public.carduri
  add column expira_la date
  generated always as (
    (make_date(2000 + substr(data_expirare, 4, 2)::integer,
               substr(data_expirare, 1, 2)::integer,
               1) + interval '1 month')::date - 1
  ) stored;

comment on column public.carduri.expira_la is 'Ultima zi valabila, derivata din data_expirare.';

-- -----------------------------------------------------------------------------
-- 3. Carduri: valori generate la insert, campuri imutabile la update
-- -----------------------------------------------------------------------------
create or replace function public.carduri_before_insert()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  -- Datele sensibile se genereaza aici, indiferent ce trimite clientul.
  new.numar_card    := public.genereaza_numar_card();
  new.ccv           := lpad(floor(random() * 1000)::integer::text, 3, '0');
  new.data_expirare := to_char(now() + interval '4 years', 'MM/YY');
  new.creat_la      := now();
  new.modificat_la  := now();

  -- Doar backend-ul poate emite un card cu sold nenul.
  if auth.role() <> 'service_role' then
    new.sold_curent := 0;
  end if;

  return new;
end;
$$;

drop trigger if exists carduri_inainte_de_insert on public.carduri;

create trigger carduri_inainte_de_insert
  before insert on public.carduri
  for each row
  execute function public.carduri_before_insert();

create or replace function public.carduri_protejeaza_campuri()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.id            := old.id;
  new.id_user       := old.id_user;
  new.numar_card    := old.numar_card;
  new.data_expirare := old.data_expirare;
  new.ccv           := old.ccv;
  new.creat_la      := old.creat_la;
  new.modificat_la  := now();

  -- Din aplicatie se poate schimba doar is_blocked; soldul vine din backend.
  if auth.role() <> 'service_role' then
    new.sold_curent := old.sold_curent;
  end if;

  return new;
end;
$$;

drop trigger if exists carduri_inainte_de_update on public.carduri;

create trigger carduri_inainte_de_update
  before update on public.carduri
  for each row
  execute function public.carduri_protejeaza_campuri();

-- -----------------------------------------------------------------------------
-- 4. Tabela de tranzactii
-- -----------------------------------------------------------------------------
create table if not exists public.tranzactii (
  id              uuid primary key default gen_random_uuid(),
  id_user_send    uuid references public.profiles (id) on delete set null,
  id_user_recieve uuid references public.profiles (id) on delete set null,
  id_card_send    uuid references public.carduri  (id) on delete set null,
  id_card_recieve uuid references public.carduri  (id) on delete set null,
  suma            numeric(14,2) not null,
  valuta          text        not null default 'RON',
  descriere       text,
  creat_la        timestamptz not null default now(),

  constraint tranzactii_suma_check      check (suma > 0),
  constraint tranzactii_valuta_check    check (valuta ~ '^[A-Z]{3}$'),
  constraint tranzactii_parti_check     check (id_user_send is not null or id_user_recieve is not null),
  constraint tranzactii_autotransfer_ck check (
    id_card_send is null or id_card_recieve is null or id_card_send <> id_card_recieve
  )
);

comment on table  public.tranzactii is 'Istoric de transferuri intre carduri. Randurile se pastreaza si dupa stergerea unui card sau profil (referintele devin null).';
comment on column public.tranzactii.suma      is 'Suma transferata, strict pozitiva.';
comment on column public.tranzactii.descriere is 'Detaliile platii, completate de expeditor.';

create index if not exists tranzactii_send_idx    on public.tranzactii (id_user_send, creat_la desc);
create index if not exists tranzactii_recieve_idx on public.tranzactii (id_user_recieve, creat_la desc);

-- -----------------------------------------------------------------------------
-- 5. RLS
-- -----------------------------------------------------------------------------
alter table public.carduri    enable row level security;
alter table public.tranzactii enable row level security;

drop policy if exists "carduri proprii: select" on public.carduri;
create policy "carduri proprii: select"
  on public.carduri
  for select
  to authenticated
  using (auth.uid() = id_user);

drop policy if exists "carduri proprii: insert" on public.carduri;
create policy "carduri proprii: insert"
  on public.carduri
  for insert
  to authenticated
  with check (auth.uid() = id_user);

drop policy if exists "carduri proprii: update" on public.carduri;
create policy "carduri proprii: update"
  on public.carduri
  for update
  to authenticated
  using (auth.uid() = id_user)
  with check (auth.uid() = id_user);

-- Cardurile nu se sterg din aplicatie, se blocheaza (is_blocked).

drop policy if exists "tranzactii proprii: select" on public.tranzactii;
create policy "tranzactii proprii: select"
  on public.tranzactii
  for select
  to authenticated
  using (auth.uid() in (id_user_send, id_user_recieve));

-- Nu exista politica de INSERT: tranzactiile se scriu doar din backend, ca sa
-- ramana atomice cu actualizarea soldurilor.

grant select, insert, update on public.carduri    to authenticated;
grant select                 on public.tranzactii to authenticated;

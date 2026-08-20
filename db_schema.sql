-- =============================================================================
-- Libra — schema bazei de date (referinta)
--
-- Acest fisier aduna structura tuturor tabelelor din public, ca sa fie usor de
-- citit intr-un singur loc. NU se ruleaza la deploy — sursa de adevar sunt
-- migratiile din supabase/migrations/, care contin si functiile, trigger-ele
-- si politicile RLS:
--
--   0001_profiles.sql            profiles + trigger pe auth.users + IBAN
--   0002_carduri_tranzactii.sql  carduri + tranzactii + generator de card
--   0003_card_style.sql          coloana card_style (standard | silver | gold)
--   0004_ai_asistent.sql                    conversatii, memorie, RAG si telemetrie AI
--   0005_ai_asistent_atasamente_voce.sql    atasamente PDF/poze + coloana canal
--   0006_ai_asistent_nivel_incredere.sql    nivel de incredere pe mesajele asistentului
--   0007_identity_verification.sql          verificare identitate (OCR buletin + DeepFace)
--
-- Relatii:
--   auth.users 1 ── 1 profiles 1 ── N carduri 1 ── N tranzactii
--
-- Tabelele conturi_bancare si groups (folosite de frontend) au fost create
-- direct in proiectul Supabase, fara o migratie commit-uita in acest depozit
-- — nu apar mai jos din acest motiv, nu pentru ca nu ar exista.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- profiles — date de client, populate automat la inregistrare
-- -----------------------------------------------------------------------------
create table public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  nume         text        not null,
  cnp          text        not null unique,
  telefon      text        not null,
  email        text        not null unique,
  iban_cont    text        not null unique,
  creat_la     timestamptz not null default now(),
  modificat_la timestamptz not null default now(),

  constraint profiles_nume_check    check (char_length(btrim(nume)) between 3 and 120),
  constraint profiles_cnp_check     check (cnp ~ '^[1-8][0-9]{12}$'),
  constraint profiles_telefon_check check (telefon ~ '^\+40[0-9]{9}$'),
  constraint profiles_email_check   check (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  constraint profiles_iban_check    check (iban_cont ~ '^RO[0-9]{2}[A-Z0-9]{20}$')
);

create index profiles_email_idx on public.profiles (email);

-- RLS: fiecare utilizator vede si editeaza doar randul cu id = auth.uid().
-- Insert/delete doar prin trigger-ul de pe auth.users.


-- -----------------------------------------------------------------------------
-- carduri — cardurile emise pe un profil
-- -----------------------------------------------------------------------------
create table public.carduri (
  id            uuid          primary key default gen_random_uuid(),
  id_user       uuid          not null references public.profiles (id) on delete cascade,
  numar_card    text          not null unique,          -- 16 cifre, valid Luhn — generat in trigger
  data_expirare text          not null,                 -- MM/YY (ex. 08/30) — generat in trigger
  ccv           text          not null,                 -- 3 cifre — generat in trigger
  card_style    text          not null default 'standard', -- standard | silver | gold
  sold_curent   numeric(14,2) not null default 0,       -- RON
  is_blocked    boolean       not null default false,
  creat_la      timestamptz   not null default now(),
  modificat_la  timestamptz   not null default now(),

  -- Ultima zi valabila, derivata din data_expirare (coloana generata).
  expira_la date generated always as (
    (make_date(2000 + substr(data_expirare, 4, 2)::integer,
               substr(data_expirare, 1, 2)::integer,
               1) + interval '1 month')::date - 1
  ) stored,

  constraint carduri_numar_check    check (numar_card ~ '^[0-9]{16}$'),
  constraint carduri_expirare_check check (data_expirare ~ '^(0[1-9]|1[0-2])/[0-9]{2}$'),
  constraint carduri_ccv_check      check (ccv ~ '^[0-9]{3}$'),
  constraint carduri_sold_check     check (sold_curent >= 0),
  constraint carduri_stil_check     check (card_style in ('standard', 'silver', 'gold'))
);

create index carduri_id_user_idx on public.carduri (id_user);

-- Un profil nou nu are niciun card — se creeaza doar la cererea utilizatorului
-- (alege tematica; numar_card, ccv, data_expirare se genereaza in trigger la
-- insert, indiferent ce trimite clientul).
-- RLS: select/insert/update pe cardurile proprii; delete nu e permis (se
-- foloseste is_blocked). sold_curent, numar_card, ccv, data_expirare si
-- card_style sunt imutabile din client dupa creare; sold_curent se seteaza
-- doar din backend (service_role) si la insert.


-- -----------------------------------------------------------------------------
-- tranzactii — istoric de transferuri intre carduri
-- -----------------------------------------------------------------------------
create table public.tranzactii (
  id              uuid          primary key default gen_random_uuid(),
  id_user_send    uuid          references public.profiles (id) on delete set null,
  id_user_recieve uuid          references public.profiles (id) on delete set null,
  id_card_send    uuid          references public.carduri  (id) on delete set null,
  id_card_recieve uuid          references public.carduri  (id) on delete set null,
  suma            numeric(14,2) not null,
  valuta          text          not null default 'RON',
  descriere       text,
  creat_la        timestamptz   not null default now(),

  constraint tranzactii_suma_check      check (suma > 0),
  constraint tranzactii_valuta_check    check (valuta ~ '^[A-Z]{3}$'),
  constraint tranzactii_parti_check     check (id_user_send is not null or id_user_recieve is not null),
  constraint tranzactii_autotransfer_ck check (
    id_card_send is null or id_card_recieve is null or id_card_send <> id_card_recieve
  )
);

create index tranzactii_send_idx    on public.tranzactii (id_user_send, creat_la desc);
create index tranzactii_recieve_idx on public.tranzactii (id_user_recieve, creat_la desc);

-- Referintele sunt "on delete set null" ca istoricul sa supravietuiasca
-- inchiderii unui card sau stergerii unui cont.
-- RLS: select daca auth.uid() e expeditor sau destinatar. Insert doar din
-- backend, ca scrierea tranzactiei si actualizarea soldurilor sa fie atomice.


-- -----------------------------------------------------------------------------
-- asistent AI — vezi 0004_ai_asistent.sql pentru definitia completa (coloane,
-- constrangeri, RLS, functia match_knowledge_chunks). Rezumat aici doar ca sa
-- ramana usor de citit structura generala:
--
--   ai_conversations, ai_messages, ai_conversation_summaries   — sesiuni de chat, proprietar id_user
--   ai_user_memories                                           — memorie per utilizator, expirabila
--   knowledge_documents, knowledge_chunks                      — corpus RAG indexat, partajat, doar citire pentru client
--   embedding_cache, query_embedding_cache                     — cache de vectori, doar service_role
--   agent_runs, tool_invocations, ai_usage_records             — telemetrie AI, fara continut de mesaj, doar service_role
--
-- Relatii noi:
--   profiles 1 ── N ai_conversations 1 ── N ai_messages
--   ai_conversations 1 ── 1 ai_conversation_summaries
-- -----------------------------------------------------------------------------

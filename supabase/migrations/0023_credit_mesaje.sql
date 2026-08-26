-- =============================================================================
-- Libra — firul de discutie pe dosarul de credit
--
-- 0019 a pus mesajul analistului intr-o coloana pe cerere. A functionat, dar
-- cu o limita descoperita la prima folosire: **o coloana tine un singur mesaj**.
-- Al doilea il suprascria pe primul, deci nu exista istoric, iar clientul n-avea
-- unde raspunde daca nu intelegea ce i se cere.
--
-- Aici coloana devine tabela. Firul e in ambele sensuri, iar incarcarile de
-- documente lasa si ele un mesaj, ca dosarul sa aiba o singura cronologie:
-- "s-a cerut X -> a venit Y".
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Mesajele
--
-- Separat de `credit_evenimente` dinadins. Acolo se scrie ce a facut sistemul
-- (audit, doar-adaugare, nemodificabil); aici, ce si-au spus oamenii. Amestecate,
-- jurnalul de audit ar deveni editabil din interfata.
--
-- `id_document` leaga mesajul de fisierul incarcat, cand mesajul e chiar despre
-- el. `on delete set null`: documentul se sterge dupa retentie (0015), dar
-- mesajul ramane — altfel s-ar pierde tocmai urma ca a fost trimis ceva.
-- -----------------------------------------------------------------------------
create table if not exists public.credit_mesaje (
  id           uuid primary key default gen_random_uuid(),
  id_cerere    uuid        not null references public.credit_cereri (id) on delete cascade,
  autor        text        not null,
  id_autor     uuid        references public.profiles (id) on delete set null,
  text         text        not null,
  id_document  uuid        references public.credit_documente (id) on delete set null,
  creat_la     timestamptz not null default now(),

  constraint credit_mesaje_autor_check check (autor in ('client', 'analist', 'sistem')),
  constraint credit_mesaje_text_check
    check (char_length(btrim(text)) between 1 and 2000)
);

comment on table public.credit_mesaje is
  'Firul de discutie dintre client si analist pe o cerere de credit. Continut scris de oameni — audit-ul sta separat, in credit_evenimente.';
comment on column public.credit_mesaje.autor is
  'client | analist | sistem. "sistem" e pentru mesajele generate automat, ca cel de la incarcarea unui document.';
comment on column public.credit_mesaje.id_document is
  'Completat cand mesajul insoteste un document incarcat. Ramane null dupa stergerea fisierului la retentie; mesajul supravietuieste.';

-- Firul se citeste mereu intreg, in ordine cronologica.
create index if not exists credit_mesaje_cerere_idx
  on public.credit_mesaje (id_cerere, creat_la);


-- -----------------------------------------------------------------------------
-- 2. Securitate — acelasi tipar ca credit_ai_* (0018)
--
-- RLS activat, nicio politica pentru 'authenticated': firul se citeste si se
-- scrie prin backend, cu service_role, dupa ce acesta verifica proprietatea
-- cererii. Clientul nu atinge tabela direct.
-- -----------------------------------------------------------------------------
alter table public.credit_mesaje enable row level security;


-- -----------------------------------------------------------------------------
-- 3. Mesajele existente se muta, apoi coloanele dispar
--
-- Stergerea e o abatere asumata de la regula "strict aditiv" (REGULI.md #3):
-- coloanele au fost adaugate in 0019, in aceeasi zi, sunt folosite doar de codul
-- scris atunci si n-au alt consumator. Lasate in urma ar fi o capcana — o
-- coloana care pare sa contina mesajul, dar contine doar ultimul.
--
-- Ordinea conteaza: intai se copiaza, apoi se sterge. `coalesce` acopera
-- randurile scrise inainte ca `mesaj_analist_la` sa existe.
-- -----------------------------------------------------------------------------
insert into public.credit_mesaje (id_cerere, autor, text, creat_la)
select id, 'analist', mesaj_analist, coalesce(mesaj_analist_la, modificat_la)
  from public.credit_cereri
 where mesaj_analist is not null
   and char_length(btrim(mesaj_analist)) > 0;

alter table public.credit_cereri
  drop column if exists mesaj_analist,
  drop column if exists mesaj_analist_la;

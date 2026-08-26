-- =============================================================================
-- 0039 — Sesizarile clientului catre banca
--
-- Pana acum comunicarea mergea intr-un singur sens: `notificari` duce mesajele
-- bancii catre client, iar `credit_mesaje` e firul de discutie de pe o cerere de
-- credit. Un om caruia i s-a blocat contul si care vorbeste cu asistentul n-avea
-- unde sa ceara ajutor: putea doar sa sune.
--
-- Tabela asta e celalalt sens. Nu inlocuieste telefonul — pentru fraude in curs,
-- 0800 970 501 ramane raspunsul corect, iar asistentul il da primul — dar da o
-- cale scrisa, cu urma, pentru cazurile care nu sunt urgente.
--
-- Rezumatul e scris de asistent si CONFIRMAT de client inainte sa plece. Nu se
-- trimite nimic in numele cuiva fara ca omul sa fi vazut exact ce se trimite si
-- sa fi apasat.
-- =============================================================================

create table if not exists public.cereri_suport (
  id            uuid primary key default gen_random_uuid(),
  id_utilizator uuid        not null references public.profiles (id) on delete cascade,

  subiect       text        not null,
  rezumat       text        not null,

  -- Ce stia asistentul cand a scris rezumatul: conturi blocate, mesaje ale
  -- bancii, intrebarea din care a pornit. Pastrat ca sa poata fi citit de
  -- administrator fara sa reconstruiasca discutia, si ca sa se vada pe ce s-a
  -- bazat rezumatul daca se dovedeste gresit.
  context       jsonb       not null default '{}'::jsonb,

  status        text        not null default 'deschisa',

  -- Raspunsul administratorului. Ajunge la client ca notificare.
  raspuns          text,
  id_administrator uuid     references public.profiles (id) on delete set null,
  raspuns_la       timestamptz,

  creat_la      timestamptz not null default now(),

  constraint cereri_suport_status_check check (status in ('deschisa', 'in_lucru', 'rezolvata')),
  constraint cereri_suport_subiect_check check (char_length(btrim(subiect)) between 3 and 200),
  constraint cereri_suport_rezumat_check check (char_length(btrim(rezumat)) between 10 and 4000),
  constraint cereri_suport_raspuns_check check (raspuns is null or char_length(btrim(raspuns)) between 1 and 4000)
);

comment on table public.cereri_suport is
  'Sesizari trimise de client catre banca, pornite din conversatia cu asistentul.';
comment on column public.cereri_suport.rezumat is
  'Scris de asistent, confirmat de client inainte de trimitere.';
comment on column public.cereri_suport.context is
  'Ce stia asistentul in momentul redactarii — pentru administrator si pentru audit.';

create index if not exists cereri_suport_utilizator_idx
  on public.cereri_suport (id_utilizator, creat_la desc);

-- Coada administratorului: cele nerezolvate, cele mai vechi primele. Un om care
-- asteapta de trei zile trebuie sa fie deasupra celui care a scris acum o ora.
create index if not exists cereri_suport_deschise_idx
  on public.cereri_suport (creat_la)
  where status <> 'rezolvata';

alter table public.cereri_suport enable row level security;

-- Clientul isi vede propriile sesizari; administratorul le vede pe toate.
drop policy if exists "sesizari proprii: select" on public.cereri_suport;
create policy "sesizari proprii: select"
  on public.cereri_suport for select to authenticated
  using (auth.uid() = id_utilizator or public.este_administrator());

-- Scrierea merge prin backend, cu service-role, dupa ce clientul a confirmat.
-- Nicio politica de insert pentru 'authenticated': o sesizare nu trebuie sa
-- poata fi fabricata direct din browser, cu alt rezumat decat cel aratat.

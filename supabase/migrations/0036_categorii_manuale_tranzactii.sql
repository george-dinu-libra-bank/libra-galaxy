-- =============================================================================
-- 0036 — categorie manuala pentru o tranzactie, cand utilizatorul confirma
--
-- Categoria unei tranzactii e azi mereu determinista (tools/categorii_tranzactii.py,
-- din descriere/contraparte) — bun implicit, dar unele plati (ex. un transfer
-- catre un comerciant necunoscut) cad pe "altele" desi omul stie exact ce a fost.
--
-- Fluxul nou de atasamente in asistent (poza/chitanta) ii da o cale sa spuna
-- explicit: "leaga asta de tranzactia de 150 lei, e restaurant". Asistentul
-- doar SUGEREAZA, printr-un buton — scrierea reala se intampla determinist,
-- prin ruta apelata de acel buton, niciodata direct de model (CLAUDE.md #9).
-- =============================================================================

create table if not exists public.categorii_manuale_tranzactii (
  id_tranzactie uuid primary key references public.tranzactii (id) on delete cascade,
  id_user       uuid not null references public.profiles (id) on delete cascade,
  categorie     text not null,
  creat_la      timestamptz not null default now(),

  constraint categorii_manuale_categorie_check check (
    categorie in (
      'transfer', 'masina', 'cumparaturi', 'utilitati', 'restaurant',
      'sanatate', 'abonamente', 'locuinta', 'salariu', 'altele'
    )
  )
);

comment on table public.categorii_manuale_tranzactii is
  'Suprascrie categoria determinista (tools/categorii_tranzactii.py) pentru o tranzactie anume, cand utilizatorul confirma explicit din asistent. O tranzactie are cel mult o suprascriere (primary key = id_tranzactie).';
comment on column public.categorii_manuale_tranzactii.id_user is
  'Utilizatorul care a confirmat. Verificat, la scriere, ca fiind chiar participantul la tranzactie — vezi politica de insert/update de mai jos si api/routes/analiza.py.';

-- -----------------------------------------------------------------------------
-- RLS — la fel ca tranzactii (0002): AnalizaService citeste cu clientul
-- utilizatorului (RLS filtreaza), iar scrierea (ruta /analiza/categorii-manuale)
-- merge tot cu acel client, nu cu service_role. Aparare in doi timpi la scriere:
-- Python verifica intai explicit ca tranzactia apartine utilizatorului (mesaj de
-- eroare clar), iar politica de mai jos repeta aceeasi verificare in baza de
-- date, ca o eventuala scapare in cod sa nu devina o gaura reala.
-- -----------------------------------------------------------------------------
alter table public.categorii_manuale_tranzactii enable row level security;

drop policy if exists "categorii manuale proprii: select" on public.categorii_manuale_tranzactii;
create policy "categorii manuale proprii: select"
  on public.categorii_manuale_tranzactii
  for select
  to authenticated
  using (auth.uid() = id_user);

drop policy if exists "categorii manuale proprii: insert" on public.categorii_manuale_tranzactii;
create policy "categorii manuale proprii: insert"
  on public.categorii_manuale_tranzactii
  for insert
  to authenticated
  with check (
    auth.uid() = id_user
    and exists (
      select 1 from public.tranzactii t
       where t.id = id_tranzactie
         and auth.uid() in (t.id_user_send, t.id_user_recieve)
    )
  );

drop policy if exists "categorii manuale proprii: update" on public.categorii_manuale_tranzactii;
create policy "categorii manuale proprii: update"
  on public.categorii_manuale_tranzactii
  for update
  to authenticated
  using (auth.uid() = id_user)
  with check (auth.uid() = id_user);

grant select, insert, update on public.categorii_manuale_tranzactii to authenticated;

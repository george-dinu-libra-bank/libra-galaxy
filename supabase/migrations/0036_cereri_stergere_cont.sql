-- =============================================================================
-- 0036 — Clientul isi poate cere stergerea contului, banca decide
--
-- Pana acum nu exista niciun drum prin care cineva sa ceara asta din aplicatie.
-- Se putea doar din afara — cineva stergea randul din `profiles` de mana, si
-- exact asa a aparut bug-ul reparat in 0034.
--
-- CERERE, nu stergere pe loc. Doua motive, amandoua tin de banca, nu de cod:
-- o banca nu inchide un client cat timp are un credit in derulare sau bani in
-- cont, iar stergerea e ireversibila, deci trece pe la un om. Acelasi tipar ca
-- la creditare: clientul cere, analistul decide.
--
-- Stergerea propriu-zisa NU se face de aici si nici automat la aprobare.
-- Aprobarea marcheaza doar ca banca e de acord; stergerea ramane un pas
-- separat, facut de administrator. Un buton care sterge ireversibil un client,
-- la prima livrare a functiei, nu merita riscul.
-- =============================================================================

create table if not exists public.cereri_stergere_cont (
  id             uuid primary key default gen_random_uuid(),
  id_utilizator  uuid not null references public.profiles (id) on delete cascade,
  motiv          text,
  status         text not null default 'in_asteptare'
                 check (status in ('in_asteptare', 'aprobata', 'respinsa', 'retrasa')),
  creat_la       timestamptz not null default now(),
  decis_la       timestamptz,
  id_admin       uuid references public.profiles (id) on delete set null,
  motiv_refuz    text
);

comment on table public.cereri_stergere_cont is
  'Cereri de inchidere a contului, depuse de client si decise de banca. '
  'Aprobarea nu sterge nimic — stergerea ramane o actiune separata de admin.';

comment on column public.cereri_stergere_cont.motiv is
  'De ce pleaca clientul. Optional: nu conditionam plecarea de o explicatie.';

comment on column public.cereri_stergere_cont.status is
  '"retrasa" e a clientului (s-a razgandit), "respinsa" e a bancii. Doua '
  'cuvinte diferite fiindca sunt doua lucruri diferite in jurnal.';

-- `on delete cascade` pe id_utilizator: cand contul chiar dispare, cererea lui
-- n-are de ce sa ramana. Pe id_admin, `set null`: daca pleaca analistul din
-- banca, decizia lui ramane in picioare, doar ca fara nume.

-- O singura cerere deschisa per utilizator. Index partial, nu constrangere pe
-- toata coloana: cine a fost respins o data trebuie sa poata cere din nou.
create unique index if not exists cereri_stergere_cont_una_deschisa_idx
  on public.cereri_stergere_cont (id_utilizator)
  where status = 'in_asteptare';

-- Coada analistului: cele in asteptare, cele mai vechi intai.
create index if not exists cereri_stergere_cont_coada_idx
  on public.cereri_stergere_cont (status, creat_la);


-- -----------------------------------------------------------------------------
-- RLS — acelasi tipar ca `notificari` (0020)
-- -----------------------------------------------------------------------------

alter table public.cereri_stergere_cont enable row level security;

drop policy if exists "cereri stergere: select" on public.cereri_stergere_cont;
create policy "cereri stergere: select"
  on public.cereri_stergere_cont for select to authenticated
  using (auth.uid() = id_utilizator or public.este_administrator());

drop policy if exists "cereri stergere: depune" on public.cereri_stergere_cont;
create policy "cereri stergere: depune"
  on public.cereri_stergere_cont for insert to authenticated
  with check (auth.uid() = id_utilizator);

-- Clientul isi poate doar RETRAGE cererea. Nu si-o poate aproba singur: `using`
-- il lasa doar pe randurile lui inca in asteptare, iar triggerul de mai jos
-- verifica in ce stare o duce. Fara el, un client ar putea scrie
-- status = 'aprobata' direct prin PostgREST.
drop policy if exists "cereri stergere: retrage" on public.cereri_stergere_cont;
create policy "cereri stergere: retrage"
  on public.cereri_stergere_cont for update to authenticated
  using (
    (auth.uid() = id_utilizator and status = 'in_asteptare')
    or public.este_administrator()
  )
  with check (auth.uid() = id_utilizator or public.este_administrator());


create or replace function public.cereri_stergere_pastreaza_decizia()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- Administratorul decide orice; clientul poate duce cererea doar spre
  -- 'retrasa'. Verificarea sta in trigger, nu doar in politica, fiindca
  -- `with check` nu poate compara starea veche cu cea noua.
  if public.este_administrator() then
    return new;
  end if;

  if new.status is distinct from old.status and new.status <> 'retrasa' then
    raise exception 'DECIZIE_REZERVATA_BANCII'
      using detail = 'Doar banca poate aproba sau respinge o cerere de stergere.';
  end if;

  -- Nici motivul de refuz, nici analistul nu sunt ale clientului.
  new.id_admin    := old.id_admin;
  new.motiv_refuz := old.motiv_refuz;
  new.decis_la    := old.decis_la;

  return new;
end;
$$;

drop trigger if exists cereri_stergere_pastreaza_decizia on public.cereri_stergere_cont;
create trigger cereri_stergere_pastreaza_decizia
  before update on public.cereri_stergere_cont
  for each row execute function public.cereri_stergere_pastreaza_decizia();

revoke all on function public.cereri_stergere_pastreaza_decizia() from public, anon, authenticated;

-- =============================================================================
-- Libra — plati de card confirmate din aplicatie (demo)
--
-- Fluxul: magazinul (/shop) cere o plata cu datele unui card Libra, plata se
-- naste in PENDING_APPROVAL, iar utilizatorul o confirma sau o respinge din
-- aplicatia de banking. Banii se misca abia la confirmare.
--
-- Sistem didactic: cardurile sunt fictive, nu exista procesator real de plati.
-- CVV-ul se verifica la creare, dar nu se salveaza niciodata in public.payments.
--
-- Ca peste tot in proiect, logica bancara sta in functii SQL apelate cu
-- service_role din server: clientul are doar drept de citire pe randurile lui.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Tabela
-- -----------------------------------------------------------------------------
create table if not exists public.payments (
  id              uuid primary key default gen_random_uuid(),
  id_user         uuid        not null references public.profiles (id)         on delete cascade,
  id_card         uuid        not null references public.carduri (id)          on delete cascade,
  -- Contul din care se ia suma. Banii nu stau pe card (0007_conturi_bancare.sql).
  id_cont         uuid                 references public.conturi_bancare (id)  on delete set null,
  card_ultimele4  text        not null,
  suma            numeric(14,2) not null,
  valuta          text        not null default 'RON',
  comerciant      text        not null,
  descriere       text,
  status          text        not null default 'PENDING_APPROVAL',
  -- De ce a esuat sau a fost oprita plata; null cat timp merge bine.
  motiv           text,
  creat_la        timestamptz not null default now(),
  modificat_la    timestamptz not null default now(),
  expira_la       timestamptz,

  constraint payments_suma_check    check (suma > 0),
  constraint payments_valuta_check  check (valuta ~ '^[A-Z]{3}$'),
  constraint payments_ultime4_check check (card_ultimele4 ~ '^[0-9]{4}$'),
  constraint payments_status_check  check (
    status in ('PENDING_APPROVAL', 'APPROVED', 'DECLINED', 'EXPIRED', 'FAILED')
  )
);

comment on table  public.payments is 'Cereri de plata la comerciant, confirmate din aplicatia de banking.';
comment on column public.payments.id_cont        is 'Contul debitat la aprobare, ales la creare dintre conturile utilizatorului.';
comment on column public.payments.card_ultimele4 is 'Ultimele 4 cifre, ca drawerul de confirmare sa nu mai interogheze cardul.';
comment on column public.payments.suma           is 'Suma ceruta de comerciant, in valuta comerciantului.';
comment on column public.payments.expira_la      is 'Dupa acest moment plata nu mai poate fi aprobata.';

-- Drawerul de confirmare cauta exact plafonul „ale mele, in asteptare".
create index if not exists payments_user_status_idx
  on public.payments (id_user, status, creat_la desc);

-- -----------------------------------------------------------------------------
-- 2. Realtime
--
-- Ambele ecrane asculta prin postgres_changes: checkout-ul filtrat pe o singura
-- plata (id=eq.…), dashboard-ul pe id_user. Filtrele pe UPDATE au nevoie de
-- randul intreg, deci replica identity full.
-- -----------------------------------------------------------------------------
alter table public.payments replica identity full;

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
     and not exists (
       select 1 from pg_publication_tables
       where pubname = 'supabase_realtime'
         and schemaname = 'public'
         and tablename = 'payments'
     )
  then
    execute 'alter publication supabase_realtime add table public.payments';
  end if;
end;
$$;

-- -----------------------------------------------------------------------------
-- 3. RLS
--
-- Citire: doar platile proprii. Scriere: niciuna din client — statusul se
-- schimba exclusiv prin functiile de mai jos, apelate cu service_role.
-- -----------------------------------------------------------------------------
alter table public.payments enable row level security;

drop policy if exists "plati proprii: select" on public.payments;
create policy "plati proprii: select"
  on public.payments
  for select
  to authenticated
  using (auth.uid() = id_user);

revoke all on public.payments from anon, authenticated;
grant select on public.payments to authenticated;

-- -----------------------------------------------------------------------------
-- 4. Ultima zi valabila a unui card
--
-- public.carduri tine expirarea ca text „MM/YY". Coloana derivata `expira_la`
-- descrisa in 0002_carduri_tranzactii.sql nu exista in baza, asa ca data se
-- calculeaza aici: prima zi a lunii urmatoare, minus o zi.
-- -----------------------------------------------------------------------------
create or replace function public.card_expira_la(p_data_expirare text)
returns date
language sql
immutable
set search_path = ''
as $$
  select (make_date(2000 + substr(p_data_expirare, 4, 2)::integer,
                    substr(p_data_expirare, 1, 2)::integer,
                    1) + interval '1 month')::date - 1;
$$;

comment on function public.card_expira_la is
  'Ultima zi in care un card cu data_expirare „MM/YY" mai este valabil.';

-- -----------------------------------------------------------------------------
-- 5. Creare — magazinul cere plata
--
-- Ridica exceptii cu codul in `message` si textul lung in `detail`, ca
-- public.core_banking (0004_core_banking.sql).
-- -----------------------------------------------------------------------------
create or replace function public.creeaza_plata(
  p_id_user       uuid,
  p_numar_card    text,
  p_data_expirare text,
  p_ccv           text,
  p_suma          numeric,
  p_comerciant    text,
  p_descriere     text    default null,
  p_valuta        text    default 'RON',
  p_secunde       integer default 120
)
returns public.payments
language plpgsql
volatile
set search_path = ''
as $$
declare
  v_card      public.carduri%rowtype;
  v_cont      public.conturi_bancare%rowtype;
  v_id_ales   uuid;
  v_plata     public.payments%rowtype;
  v_numar     text          := regexp_replace(coalesce(p_numar_card, ''), '\D', '', 'g');
  v_suma      numeric(14,2) := round(coalesce(p_suma, 0), 2);
  v_in_cont   numeric(14,2);
begin
  if p_id_user is null then
    raise exception 'NEAUTENTIFICAT' using detail = 'Plata cere un utilizator autentificat.';
  end if;

  if v_suma <= 0 then
    raise exception 'SUMA_INVALIDA' using detail = 'Suma platii trebuie sa fie strict pozitiva.';
  end if;

  if coalesce(p_valuta, '') !~ '^[A-Z]{3}$' then
    raise exception 'VALUTA_NESUPORTATA' using detail = 'Valuta platii trebuie sa fie un cod ISO de trei litere.';
  end if;

  -- Cardul trebuie sa fie al celui care plateste. Un card inexistent si un card
  -- al altcuiva primesc acelasi raspuns: altfel formularul de checkout devine un
  -- oracol prin care se pot ghici numere de card valide.
  select c.* into v_card
  from public.carduri c
  where c.numar_card = v_numar
    and c.id_user = p_id_user;

  if not found
     or v_card.data_expirare is distinct from p_data_expirare
     or v_card.ccv is distinct from p_ccv
  then
    raise exception 'DATE_CARD_GRESITE'
      using detail = 'Numarul, data de expirare sau CVV-ul nu corespund unui card al utilizatorului.';
  end if;

  if v_card.is_blocked then
    raise exception 'CARD_BLOCAT' using detail = 'Cardul este blocat din aplicatie.';
  end if;

  if public.card_expira_la(v_card.data_expirare) < current_date then
    raise exception 'CARD_EXPIRAT' using detail = 'Cardul a expirat.';
  end if;

  -- Se alege contul din care s-ar plati: intai unul in valuta comerciantului,
  -- apoi cel mai vechi. Primul care acopera suma castiga.
  for v_cont in
    select c.*
    from public.conturi_bancare c
    where c.id_user = p_id_user
    order by (c.valuta = p_valuta) desc, c.creat_la asc
  loop
    begin
      v_in_cont := public.converteste(v_suma, p_valuta, v_cont.valuta);
    exception when others then
      -- Un cont a carui valuta n-are inca un curs BNR nu poate fi evaluat; il
      -- sarim in loc sa oprim plata. Orice alta eroare merge mai departe.
      if sqlerrm <> 'CURS_INDISPONIBIL' then
        raise;
      end if;
      v_in_cont := null;
    end;

    if v_in_cont is not null and v_cont.sold >= v_in_cont then
      v_id_ales := v_cont.id;
      exit;
    end if;
  end loop;

  if v_id_ales is null then
    if exists (select 1 from public.conturi_bancare c where c.id_user = p_id_user) then
      raise exception 'FONDURI_INSUFICIENTE'
        using detail = 'Niciun cont al utilizatorului nu acopera suma platii.';
    end if;

    raise exception 'FARA_CONT' using detail = 'Utilizatorul nu are niciun cont bancar.';
  end if;

  insert into public.payments (
    id_user, id_card, id_cont, card_ultimele4,
    suma, valuta, comerciant, descriere, status, expira_la
  )
  values (
    p_id_user, v_card.id, v_id_ales, right(v_card.numar_card, 4),
    v_suma, p_valuta, p_comerciant, p_descriere, 'PENDING_APPROVAL',
    now() + make_interval(secs => greatest(coalesce(p_secunde, 120), 30))
  )
  returning * into v_plata;

  return v_plata;
end;
$$;

comment on function public.creeaza_plata is
  'Valideaza datele cardului si deschide o plata in PENDING_APPROVAL. Nu misca bani si nu stocheaza CVV-ul.';

-- -----------------------------------------------------------------------------
-- 6. Trecerea intr-o stare finala
--
-- Update-ul e conditionat de PENDING_APPROVAL: doua cereri simultane nu pot
-- finaliza aceeasi plata de doua ori. A doua primeste randul asa cum e.
-- -----------------------------------------------------------------------------
create or replace function public.plata_finalizeaza(
  p_id     uuid,
  p_status text,
  p_motiv  text default null
)
returns public.payments
language plpgsql
volatile
set search_path = ''
as $$
declare
  v_plata public.payments%rowtype;
begin
  update public.payments p
     set status       = p_status,
         motiv        = p_motiv,
         modificat_la = now()
   where p.id = p_id
     and p.status = 'PENDING_APPROVAL'
  returning p.* into v_plata;

  -- Cineva a ajuns primul: se intoarce starea reala, nu o eroare.
  if not found then
    select p.* into v_plata from public.payments p where p.id = p_id;
  end if;

  return v_plata;
end;
$$;

comment on function public.plata_finalizeaza is
  'Muta o plata din PENDING_APPROVAL intr-o stare finala, o singura data.';

-- -----------------------------------------------------------------------------
-- 7. Aprobare — utilizatorul confirma din aplicatia de banking
--
-- Tot ce se verifica la creare se verifica din nou aici: intre timp cardul a
-- putut fi blocat, cursul s-a putut schimba, iar banii au putut pleca in alta
-- parte. Verificarea si debitarea stau in aceeasi tranzactie, cu lock pe cont.
-- -----------------------------------------------------------------------------
create or replace function public.aproba_plata(p_id uuid, p_id_user uuid)
returns public.payments
language plpgsql
volatile
set search_path = ''
as $$
declare
  v_plata   public.payments%rowtype;
  v_card    public.carduri%rowtype;
  v_cont    public.conturi_bancare%rowtype;
  v_in_cont numeric(14,2);
begin
  if p_id_user is null then
    raise exception 'NEAUTENTIFICAT' using detail = 'Aprobarea cere un utilizator autentificat.';
  end if;

  -- Lock pe randul platii: doua apeluri simultane se serializeaza aici, iar al
  -- doilea gaseste statusul deja schimbat.
  select p.* into v_plata
  from public.payments p
  where p.id = p_id
    and p.id_user = p_id_user
  for update;

  if not found then
    raise exception 'PLATA_INEXISTENTA' using detail = 'Plata nu exista sau nu apartine utilizatorului.';
  end if;

  -- Deja aprobata, respinsa sau expirata: nu se atinge nimic.
  if v_plata.status <> 'PENDING_APPROVAL' then
    return v_plata;
  end if;

  if v_plata.expira_la is not null and v_plata.expira_la <= now() then
    return public.plata_finalizeaza(v_plata.id, 'EXPIRED', 'Timpul de confirmare a expirat.');
  end if;

  select c.* into v_card from public.carduri c where c.id = v_plata.id_card;

  if not found or v_card.is_blocked then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Cardul este blocat sau nu mai exista.');
  end if;

  if public.card_expira_la(v_card.data_expirare) < current_date then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Cardul a expirat intre timp.');
  end if;

  -- Lock pe cont inainte de a citi soldul: fara el, doua plati aprobate in
  -- acelasi moment ar putea trece amandoua peste acelasi sold.
  select c.* into v_cont
  from public.conturi_bancare c
  where c.id = v_plata.id_cont
  for update;

  if not found then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Contul din care se platea nu mai exista.');
  end if;

  begin
    v_in_cont := public.converteste(v_plata.suma, v_plata.valuta, v_cont.valuta);
  exception when others then
    if sqlerrm <> 'CURS_INDISPONIBIL' then
      raise;
    end if;
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Cursul valutar nu este disponibil.');
  end;

  if v_cont.sold < v_in_cont then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Fonduri insuficiente in cont.');
  end if;

  update public.conturi_bancare c
     set sold         = c.sold - v_in_cont,
         modificat_la = now()
   where c.id = v_cont.id;

  -- Plata intra si in istoricul de tranzactii: comerciantul nu are cont Libra,
  -- deci partea de incasare ramane goala.
  insert into public.tranzactii (id_user_send, id_cont_send, id_card_send, suma, valuta, descriere)
  values (
    v_plata.id_user, v_cont.id, v_plata.id_card, v_in_cont, v_cont.valuta,
    coalesce(v_plata.descriere, v_plata.comerciant)
  );

  v_plata := public.plata_finalizeaza(v_plata.id, 'APPROVED', null);

  -- Soldul si istoricul s-au schimbat: ecranele deschise se reimprospateaza.
  perform public.anunta_utilizator(
    v_plata.id_user,
    'sold',
    jsonb_build_object('id_cont', v_cont.id, 'id_plata', v_plata.id)
  );

  return v_plata;
end;
$$;

comment on function public.aproba_plata is
  'Confirma o plata: revalideaza cardul, debiteaza contul si scrie tranzactia, totul atomic.';

-- -----------------------------------------------------------------------------
-- 8. Respingere
-- -----------------------------------------------------------------------------
create or replace function public.respinge_plata(p_id uuid, p_id_user uuid)
returns public.payments
language plpgsql
volatile
set search_path = ''
as $$
declare
  v_plata public.payments%rowtype;
begin
  if p_id_user is null then
    raise exception 'NEAUTENTIFICAT' using detail = 'Respingerea cere un utilizator autentificat.';
  end if;

  select p.* into v_plata
  from public.payments p
  where p.id = p_id
    and p.id_user = p_id_user
  for update;

  if not found then
    raise exception 'PLATA_INEXISTENTA' using detail = 'Plata nu exista sau nu apartine utilizatorului.';
  end if;

  if v_plata.status <> 'PENDING_APPROVAL' then
    return v_plata;
  end if;

  return public.plata_finalizeaza(v_plata.id, 'DECLINED', 'Respinsa de utilizator.');
end;
$$;

comment on function public.respinge_plata is 'Marcheaza o plata proprie drept DECLINED, o singura data.';

-- -----------------------------------------------------------------------------
-- 9. Drepturi — functiile se apeleaza doar din server, cu service_role
-- -----------------------------------------------------------------------------
revoke all on function public.creeaza_plata(uuid, text, text, text, numeric, text, text, text, integer)
  from public, anon, authenticated;
revoke all on function public.plata_finalizeaza(uuid, text, text) from public, anon, authenticated;
revoke all on function public.aproba_plata(uuid, uuid)            from public, anon, authenticated;
revoke all on function public.respinge_plata(uuid, uuid)          from public, anon, authenticated;

grant execute on function public.creeaza_plata(uuid, text, text, text, numeric, text, text, text, integer)
  to service_role;
grant execute on function public.plata_finalizeaza(uuid, text, text) to service_role;
grant execute on function public.aproba_plata(uuid, uuid)            to service_role;
grant execute on function public.respinge_plata(uuid, uuid)          to service_role;

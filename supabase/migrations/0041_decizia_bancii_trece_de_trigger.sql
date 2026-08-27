-- =============================================================================
-- 0041 — Deciziile bancii treceau de politici, dar se opreau in propriul trigger
--
-- CAUZA, gasita ruland fluxul cap-coada pe baza reala, nu citind codul:
--
--   ERROR: DECIZIE_REZERVATA_BANCII
--   CONTEXT: PL/pgSQL function public.cereri_inchidere_pastreaza_decizia()
--     SQL statement "update public.cereri_inchidere_cont set status='aprobata'..."
--     PL/pgSQL function public.inchide_cont_bancar(uuid,uuid,uuid)
--
-- Triggerele din 0036 si 0040 lasa doar administratorul sa schimbe statusul, si
-- il recunosc prin `public.este_administrator()` — care se uita la `auth.uid()`.
-- Dar RPC-urile care iau decizia sunt chemate de backend cu cheia service-role,
-- unde `auth.uid()` e NULL. Deci `este_administrator()` intoarce fals, iar
-- triggerul refuza exact operatiunea pentru care a fost scris RPC-ul.
--
-- Consecinta practica: NICIO decizie de banca nu functiona. Nici aprobarea unei
-- inchideri de cont (0040), nici aprobarea sau respingerea unei cereri de
-- inchidere a relatiei (0037). Fluxurile pareau livrate — migratiile aplicate,
-- rutele raspunzand, testele verzi — fiindca nimeni nu apasase butonul pe date
-- reale.
--
-- REPARATIA: un steag valabil doar in tranzactia curenta. RPC-urile care au
-- dreptul sa decida il ridica inainte de `update`, iar triggerul il accepta.
--
-- De ce steag si nu „lasa sa treaca orice apel fara auth.uid()": acela ar fi
-- deschis update-ul de status pentru ORICE cod care ruleaza cu service-role,
-- inclusiv o scriere gresita de altundeva. Steagul e ridicat doar de cele trei
-- functii care chiar iau decizia, si cade singur la finalul tranzactiei
-- (`set_config(..., true)` = local).
-- =============================================================================

create or replace function public.decizia_e_a_bancii()
returns boolean
language sql
stable
set search_path = ''
as $$
  -- `true` doar in interiorul unui RPC de decizie, si doar cat tine tranzactia.
  select coalesce(current_setting('app.decizie_banca', true), '') = '1';
$$;

comment on function public.decizia_e_a_bancii() is
  'Steag local de tranzactie, ridicat de RPC-urile de decizie. Le lasa sa treaca '
  'de triggerele care apara statusul cererilor, unde auth.uid() e NULL.';


-- -----------------------------------------------------------------------------
-- Triggerele accepta si steagul, pe langa administratorul autentificat
-- -----------------------------------------------------------------------------

create or replace function public.cereri_stergere_pastreaza_decizia()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- Administratorul autentificat (din aplicatie) SAU un RPC de decizie care si-a
  -- ridicat steagul. Clientul poate duce cererea doar spre 'retrasa'.
  if public.este_administrator() or public.decizia_e_a_bancii() then
    return new;
  end if;

  if new.status is distinct from old.status and new.status <> 'retrasa' then
    raise exception 'DECIZIE_REZERVATA_BANCII'
      using detail = 'Doar banca poate aproba sau respinge o cerere de stergere.';
  end if;

  new.id_admin    := old.id_admin;
  new.motiv_refuz := old.motiv_refuz;
  new.decis_la    := old.decis_la;
  return new;
end;
$$;


create or replace function public.cereri_inchidere_pastreaza_decizia()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if public.este_administrator() or public.decizia_e_a_bancii() then
    return new;
  end if;

  if new.status is distinct from old.status and new.status <> 'retrasa' then
    raise exception 'DECIZIE_REZERVATA_BANCII'
      using detail = 'Doar banca poate aproba sau respinge o cerere de inchidere.';
  end if;

  new.id_admin    := old.id_admin;
  new.motiv_refuz := old.motiv_refuz;
  new.decis_la    := old.decis_la;
  return new;
end;
$$;


-- -----------------------------------------------------------------------------
-- RPC-urile de decizie ridica steagul
--
-- Se rescriu integral (create or replace), identice cu versiunile din 0037 si
-- 0040, plus randul de `set_config`. Se pune la INCEPUT, nu chiar inaintea
-- update-ului: asa nimeni care adauga maine inca un `update` in aceeasi functie
-- nu descopera din nou, pe teren, ca triggerul il opreste.
-- -----------------------------------------------------------------------------

create or replace function public.decide_stergere_cont(
  p_id_cerere uuid,
  p_id_admin  uuid,
  p_aproba    boolean,
  p_motiv     text default null
)
returns public.cereri_stergere_cont
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_cerere public.cereri_stergere_cont%rowtype;
  v_mutari integer := 0;
  v_titlu  text;
  v_mesaj  text;
begin
  perform set_config('app.decizie_banca', '1', true);

  select c.* into v_cerere
  from public.cereri_stergere_cont c
  where c.id = p_id_cerere
  for update;

  if not found then
    raise exception 'CERERE_INEXISTENTA' using detail = 'Cererea nu exista.';
  end if;

  if v_cerere.status <> 'in_asteptare' then
    raise exception 'CERERE_DECISA'
      using detail = 'Cererea a fost deja ' || v_cerere.status || '.';
  end if;

  if p_aproba then
    select count(*) into v_mutari from public.consolideaza_conturile(v_cerere.id_utilizator);

    v_titlu := 'Cererea de inchidere a contului a fost aprobata';
    v_mesaj := 'Am aprobat cererea ta de inchidere. ';

    if v_mutari > 0 then
      v_mesaj := v_mesaj || 'Am mutat banii din ' || v_mutari ||
                 case when v_mutari = 1 then ' cont secundar' else ' conturi secundare' end ||
                 ' in contul tau principal. ';
    end if;

    v_mesaj := v_mesaj || 'Un coleg te contacteaza pentru ultimii pasi.';
  else
    v_titlu := 'Cererea de inchidere a contului a fost respinsa';
    v_mesaj := coalesce(
      nullif(trim(p_motiv), ''),
      'Cererea ta de inchidere nu a putut fi aprobata. Scrie-ne daca vrei detalii.'
    );
  end if;

  update public.cereri_stergere_cont c
     set status      = case when p_aproba then 'aprobata' else 'respinsa' end,
         decis_la    = now(),
         id_admin    = p_id_admin,
         motiv_refuz = case when p_aproba then null else nullif(trim(p_motiv), '') end
   where c.id = p_id_cerere
  returning * into v_cerere;

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (v_cerere.id_utilizator, v_titlu, v_mesaj,
          case when p_aproba then 'succes' else 'avertisment' end);

  perform public.anunta_utilizator(
    v_cerere.id_utilizator,
    'notificare',
    jsonb_build_object('id_cerere', v_cerere.id, 'status', v_cerere.status)
  );

  return v_cerere;
end;
$$;

revoke all on function public.decide_stergere_cont(uuid, uuid, boolean, text) from public, anon, authenticated;
grant execute on function public.decide_stergere_cont(uuid, uuid, boolean, text) to service_role;


-- `sterge_client` (0038) NU se atinge: verificat, nu scrie pe randul cererii —
-- profilul dispare, iar cererea pleaca odata cu el prin cascada. Deci nu trece
-- niciodata prin triggerul de mai sus si n-are nevoie de steag.

create or replace function public.inchide_cont_bancar(
  p_id_cerere     uuid,
  p_id_admin      uuid,
  p_id_destinatie uuid default null
)
returns public.cereri_inchidere_cont
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_cerere     public.cereri_inchidere_cont%rowtype;
  v_cont       public.conturi_bancare%rowtype;
  v_destinatie public.conturi_bancare%rowtype;
  v_iban_princ text;
  v_id_dest    uuid;
  v_mutat      numeric(14,2) := 0;
  v_carduri    integer := 0;
  v_mesaj      text;
begin
  perform set_config('app.decizie_banca', '1', true);

  select c.* into v_cerere
  from public.cereri_inchidere_cont c
  where c.id = p_id_cerere
  for update;

  if not found then
    raise exception 'CERERE_INEXISTENTA' using detail = 'Cererea nu exista.';
  end if;

  if v_cerere.status <> 'in_asteptare' then
    raise exception 'CERERE_DECISA'
      using detail = 'Cererea a fost deja ' || v_cerere.status || '.';
  end if;

  select c.* into v_cont
  from public.conturi_bancare c
  where c.id = v_cerere.id_cont
  for update;

  if not found then
    raise exception 'CONT_INEXISTENT' using detail = 'Contul nu mai exista.';
  end if;

  if v_cont.inchis_la is not null then
    raise exception 'CONT_DEJA_INCHIS' using detail = 'Contul e deja inchis.';
  end if;

  select p.iban_cont into v_iban_princ
  from public.profiles p where p.id = v_cerere.id_utilizator;

  if v_iban_princ is not null and v_cont.iban = v_iban_princ then
    raise exception 'CONT_PRINCIPAL'
      using detail = 'Contul principal nu se poate inchide. Pentru a pleca din banca se inchide relatia.';
  end if;

  if v_cont.blocat_administrativ then
    raise exception 'CONT_BLOCAT'
      using detail = 'Contul e blocat administrativ; se lamureste intai blocarea.';
  end if;

  if v_cont.sold < 0 then
    raise exception 'SOLD_NEGATIV'
      using detail = 'Contul are sold negativ. Se acopera inainte de inchidere.';
  end if;

  v_id_dest := coalesce(p_id_destinatie, v_cerere.id_cont_destinatie);

  if v_id_dest is null and v_iban_princ is not null then
    select c.id into v_id_dest
    from public.conturi_bancare c
    where c.id_user = v_cerere.id_utilizator
      and c.iban = v_iban_princ
      and c.inchis_la is null;
  end if;

  if v_cont.sold > 0 then
    if v_id_dest is null then
      raise exception 'FARA_DESTINATIE'
        using detail = 'Contul are sold, dar nu s-a putut alege un cont in care sa fie mutat.';
    end if;

    if v_id_dest = v_cont.id then
      raise exception 'DESTINATIE_INVALIDA'
        using detail = 'Contul destinatie nu poate fi chiar contul care se inchide.';
    end if;

    select c.* into v_destinatie
    from public.conturi_bancare c
    where c.id = v_id_dest
      and c.id_user = v_cerere.id_utilizator
      and c.inchis_la is null
    for update;

    if not found then
      raise exception 'DESTINATIE_INVALIDA'
        using detail = 'Contul destinatie nu exista, e inchis, sau e al altui client.';
    end if;

    if v_destinatie.blocat_administrativ then
      raise exception 'DESTINATIE_BLOCATA'
        using detail = 'Contul destinatie e blocat; banii n-ar mai putea fi folositi.';
    end if;

    v_mutat := public.muta_sold_intre_conturi(
      v_cont, v_destinatie, 'Transfer inainte de inchiderea contului'
    );
  end if;

  update public.carduri
     set inchis_la = now(), is_blocked = true, modificat_la = now()
   where id_cont = v_cont.id and inchis_la is null;

  get diagnostics v_carduri = row_count;

  update public.conturi_bancare c
     set inchis_la = now(), modificat_la = now()
   where c.id = v_cont.id;

  update public.cereri_inchidere_cont c
     set status = 'aprobata', decis_la = now(), id_admin = p_id_admin,
         id_cont_destinatie = v_id_dest
   where c.id = p_id_cerere
  returning * into v_cerere;

  v_mesaj := 'Contul "' || v_cont.nume || '" a fost inchis. ';

  if v_mutat > 0 then
    v_mesaj := v_mesaj || 'Am mutat ' || trim(to_char(v_mutat, 'FM999999999990.00')) ||
               ' ' || v_destinatie.valuta || ' in contul "' || v_destinatie.nume || '". ';
  end if;

  if v_carduri > 0 then
    v_mesaj := v_mesaj ||
               case when v_carduri = 1 then 'Cardul legat de el a fost inchis. '
                    else 'Cele ' || v_carduri || ' carduri legate de el au fost inchise. ' end;
  end if;

  v_mesaj := v_mesaj || 'Istoricul tranzactiilor ramane neschimbat.';

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (v_cerere.id_utilizator, 'Contul a fost inchis', v_mesaj, 'succes');

  perform public.anunta_utilizator(
    v_cerere.id_utilizator, 'notificare',
    jsonb_build_object('id_cerere', v_cerere.id, 'status', 'aprobata')
  );

  return v_cerere;
end;
$$;

revoke all on function public.inchide_cont_bancar(uuid, uuid, uuid) from public, anon, authenticated;
grant execute on function public.inchide_cont_bancar(uuid, uuid, uuid) to service_role;


create or replace function public.respinge_inchidere_cont(
  p_id_cerere uuid,
  p_id_admin  uuid,
  p_motiv     text default null
)
returns public.cereri_inchidere_cont
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_cerere public.cereri_inchidere_cont%rowtype;
  v_nume   text;
begin
  perform set_config('app.decizie_banca', '1', true);

  select c.* into v_cerere
  from public.cereri_inchidere_cont c
  where c.id = p_id_cerere
  for update;

  if not found then
    raise exception 'CERERE_INEXISTENTA' using detail = 'Cererea nu exista.';
  end if;

  if v_cerere.status <> 'in_asteptare' then
    raise exception 'CERERE_DECISA'
      using detail = 'Cererea a fost deja ' || v_cerere.status || '.';
  end if;

  select c.nume into v_nume from public.conturi_bancare c where c.id = v_cerere.id_cont;

  update public.cereri_inchidere_cont c
     set status = 'respinsa', decis_la = now(), id_admin = p_id_admin,
         motiv_refuz = nullif(trim(p_motiv), '')
   where c.id = p_id_cerere
  returning * into v_cerere;

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (
    v_cerere.id_utilizator,
    'Cererea de inchidere a contului a fost respinsa',
    coalesce(
      nullif(trim(p_motiv), ''),
      'Cererea de inchidere pentru contul "' || coalesce(v_nume, 'necunoscut') ||
      '" nu a putut fi aprobata. Scrie-ne daca vrei detalii.'
    ),
    'avertisment'
  );

  perform public.anunta_utilizator(
    v_cerere.id_utilizator, 'notificare',
    jsonb_build_object('id_cerere', v_cerere.id, 'status', 'respinsa')
  );

  return v_cerere;
end;
$$;

revoke all on function public.respinge_inchidere_cont(uuid, uuid, text) from public, anon, authenticated;
grant execute on function public.respinge_inchidere_cont(uuid, uuid, text) to service_role;

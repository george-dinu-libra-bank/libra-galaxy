-- =============================================================================
-- 0037 — Banca decide cererea de inchidere, si stie sa stranga banii intai
--
-- 0036 a adus doar cererea. Aici vine partea bancii:
--
--   1. `consolideaza_conturile` — muta soldurile din conturile secundare in
--      contul principal, ca sa nu ramana bani risipiti prin conturi pe care
--      nimeni nu-i mai deschide.
--   2. `decide_stergere_cont` — aproba sau respinge, scrie notificarea si,
--      la aprobare, consolideaza.
--
-- CONTUL PRINCIPAL nu e "primul din lista". E cel al carui IBAN sta in
-- `profiles.iban_cont` — cel deschis odata cu profilul, cel pe care clientul il
-- da mai departe. Ordinea dupa `creat_la` ar da acelasi rezultat azi si alt
-- rezultat in ziua in care cineva sterge un cont vechi.
--
-- Consolidarea NU inchide conturile secundare si nu sterge nimic. Doar aduna
-- banii intr-un loc. Stergerea ramane un pas separat, facut de administrator
-- dupa ce vede ca totul e in regula — aceeasi decizie ca in 0036, si din acelasi
-- motiv: un buton care sterge ireversibil un client, la prima livrare a
-- functiei, nu merita riscul.
-- =============================================================================

create or replace function public.consolideaza_conturile(p_id_user uuid)
returns TABLE (id_cont uuid, nume text, suma numeric, valuta text)
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_principal public.conturi_bancare%rowtype;
  v_iban_cont text;
  v_sursa     public.conturi_bancare%rowtype;
  v_in_ron    numeric(14,2);
begin
  if p_id_user is null then
    raise exception 'NEAUTENTIFICAT' using detail = 'Consolidarea cere un utilizator.';
  end if;

  select p.iban_cont into v_iban_cont from public.profiles p where p.id = p_id_user;

  if v_iban_cont is null then
    raise exception 'FARA_CONT_PRINCIPAL'
      using detail = 'Profilul nu are un IBAN de cont principal.';
  end if;

  -- Lock pe contul principal cat tine mutarea: doua consolidari simultane pe
  -- acelasi client s-ar calca una pe alta la sold.
  select c.* into v_principal
  from public.conturi_bancare c
  where c.id_user = p_id_user and c.iban = v_iban_cont
  for update;

  if not found then
    raise exception 'FARA_CONT_PRINCIPAL'
      using detail = 'Contul principal al clientului nu mai exista.';
  end if;

  if v_principal.blocat_administrativ then
    raise exception 'CONT_BLOCAT'
      using detail = 'Contul principal e blocat; deblocheaza-l inainte de consolidare.';
  end if;

  for v_sursa in
    select c.* from public.conturi_bancare c
    where c.id_user = p_id_user
      and c.id <> v_principal.id
      and c.sold > 0
    order by c.creat_la
    for update
  loop
    -- Valutele pot diferi: se converteste la cursul BNR, prin aceeasi functie
    -- pe care o foloseste si restul aplicatiei. Daca lipseste cursul, se
    -- opreste tot — mai bine nicio mutare decat una la un curs inventat.
    v_in_ron := public.converteste(v_sursa.sold, v_sursa.valuta, v_principal.valuta);

    update public.conturi_bancare c
       set sold = 0, modificat_la = now()
     where c.id = v_sursa.id;

    update public.conturi_bancare c
       set sold = c.sold + v_in_ron, modificat_la = now()
     where c.id = v_principal.id;

    -- Se scrie in istoric ca orice alta miscare de bani. Acelasi client pe
    -- ambele capete: e o mutare intre conturile lui, nu o plata.
    insert into public.tranzactii (
      id_user_send, id_cont_send, id_user_recieve, id_cont_recieve,
      suma, valuta, descriere
    )
    values (
      p_id_user, v_sursa.id, p_id_user, v_principal.id,
      v_in_ron, v_principal.valuta,
      'Consolidare inainte de inchiderea contului'
    );

    id_cont := v_sursa.id;
    nume    := v_sursa.nume;
    suma    := v_in_ron;
    valuta  := v_principal.valuta;
    return next;
  end loop;

  return;
end;
$$;

comment on function public.consolideaza_conturile(uuid) is
  'Muta soldurile conturilor secundare in contul principal (profiles.iban_cont). '
  'Nu inchide si nu sterge niciun cont. Intoarce ce a mutat, pentru notificare.';

revoke all on function public.consolideaza_conturile(uuid) from public, anon, authenticated;
grant execute on function public.consolideaza_conturile(uuid) to service_role;


-- -----------------------------------------------------------------------------
-- Decizia analistului
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
  -- Lock pe cerere: doi analisti care apasa in acelasi moment se serializeaza
  -- aici, iar al doilea gaseste cererea deja decisa.
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
    -- Banii se strang INAINTE de a marca aprobarea: daca strangerea pica
    -- (curs lipsa, cont principal blocat), cererea ramane in asteptare si
    -- analistul vede de ce. Invers, ar ramane o cerere "aprobata" peste conturi
    -- pline, si nimeni n-ar sti ca pasul a esuat.
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

  -- Ecranele deschise se reimprospateaza singure (acelasi canal ca la plati).
  perform public.anunta_utilizator(
    v_cerere.id_utilizator,
    'notificare',
    jsonb_build_object('id_cerere', v_cerere.id, 'status', v_cerere.status)
  );

  return v_cerere;
end;
$$;

comment on function public.decide_stergere_cont(uuid, uuid, boolean, text) is
  'Aproba sau respinge o cerere de inchidere. La aprobare consolideaza intai '
  'conturile; daca acel pas pica, cererea ramane in asteptare.';

revoke all on function public.decide_stergere_cont(uuid, uuid, boolean, text) from public, anon, authenticated;
grant execute on function public.decide_stergere_cont(uuid, uuid, boolean, text) to service_role;

-- =============================================================================
-- Libra — INSTANTANEU al bazei de date inainte de migrarea 0009 (creditare)
--
-- Generat automat din catalogul Postgres pe 2026-08-20, direct din
-- proiectul Supabase lldcoqbkonbnqhbqrbjr.
--
-- ATENTIE: NU se ruleaza ca migratie. E o fotografie a starii existente, pastrata
-- ca plasa de siguranta si ca documentatie — `db_schema.sql` din radacina era
-- vizibil in urma fata de realitate (nu continea payments, curs_valutar,
-- user_roles, conturi_bancare.valuta, tranzactii.id_cont_*, id_group_*).
--
-- De ce a fost nevoie: `supabase_migrations` e GOL. Schema a fost construita
-- manual in SQL Editor, deci fisierele din supabase/migrations/ descriu intentia,
-- nu starea aplicata. Fisierul asta descrie starea aplicata.
--
-- Ordinea sectiunilor: functii, coloane (comentate), constrangeri, indecsi,
-- politici RLS, triggere.
--
-- Pentru restaurare reala foloseste backupul automat Supabase (Dashboard ->
-- Database -> Backups) — fisierul asta nu contine date, doar structura si cod.
-- =============================================================================


CREATE OR REPLACE FUNCTION public.anunta_utilizator(p_id_user uuid, p_eveniment text, p_continut jsonb)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  -- La o depunere in grup nu exista beneficiar-persoana.
  if p_id_user is null then
    return;
  end if;

  begin
    perform realtime.send(p_continut, p_eveniment, 'user:' || p_id_user::text, true);
  exception when others then
    raise warning 'REALTIME_ESUAT (user=%, eveniment=%): %', p_id_user, p_eveniment, sqlerrm;
  end;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.aproba_plata(p_id uuid, p_id_user uuid)
 RETURNS payments
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
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
$function$
;
CREATE OR REPLACE FUNCTION public.card_expira_la(p_data_expirare text)
 RETURNS date
 LANGUAGE sql
 IMMUTABLE
 SET search_path TO ''
AS $function$
  select (make_date(2000 + substr(p_data_expirare, 4, 2)::integer,
                    substr(p_data_expirare, 1, 2)::integer,
                    1) + interval '1 month')::date - 1;
$function$
;
CREATE OR REPLACE FUNCTION public.carduri_protejeaza_campuri()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
begin
  new.id            := old.id;
  new.id_user       := old.id_user;
  new.numar_card    := old.numar_card;
  new.data_expirare := old.data_expirare;
  new.ccv           := old.ccv;
  new.card_style    := old.card_style;
  new.creat_la      := old.creat_la;
  new.modificat_la  := now();

  -- Soldul se schimba doar din backend (service_role) sau din core_banking.
  if auth.role() <> 'service_role'
     and coalesce(current_setting('app.core_banking', true), 'off') <> 'on' then
    new.sold_curent := old.sold_curent;
  end if;

  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.conturi_anunta_sold_realtime()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  begin
    perform public.anunta_utilizator(new.id_user, 'sold', jsonb_build_object(
      'id_cont', new.id,
      'sold',    new.sold,
      'delta',   new.sold - old.sold
    ));
  exception when others then
    raise warning 'REALTIME_SOLD_ESUAT (cont=%): %', new.id, sqlerrm;
  end;

  return null;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.conturi_modificat_la()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
begin
  new.id       := old.id;
  new.id_user  := old.id_user;
  new.iban     := old.iban;
  new.creat_la := old.creat_la;
  new.modificat_la := now();
  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.converteste(p_suma numeric, p_din text, p_in text)
 RETURNS numeric
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if p_din = p_in then
    return round(p_suma, 2);
  end if;

  -- Prin RON, care e numitorul comun al tabelei: suma -> RON -> valuta tinta.
  return round(p_suma * public.curs_ron(p_din) / public.curs_ron(p_in), 2);
end;
$function$
;
CREATE OR REPLACE FUNCTION public.core_banking(p_iban_dest text, p_suma numeric, p_descriere text DEFAULT NULL::text, p_valuta text DEFAULT NULL::text, p_id_cont_send uuid DEFAULT NULL::uuid, p_id_user uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_user     uuid;
  -- service_role, sau o sesiune SQL directa (fara JWT, deci deja privilegiata).
  v_este_srv boolean := coalesce(auth.role(), 'service_role') = 'service_role';
  v_iban     text;
  v_id_send  uuid;
  v_id_recv  uuid;
  v_send     public.conturi_bancare%rowtype;
  v_recv     public.conturi_bancare%rowtype;
  v_nume_recv text;
  v_suma     numeric(14,2);
  v_primit   numeric(14,2);
  v_tranz    public.tranzactii%rowtype;
begin
  -- ---------------------------------------------------------------------------
  -- Cine face plata
  -- ---------------------------------------------------------------------------
  if v_este_srv then
    v_user := coalesce(p_id_user, auth.uid());
  else
    v_user := auth.uid();

    if p_id_user is not null and p_id_user <> v_user then
      raise exception 'NEAUTORIZAT'
        using detail = 'Nu poti initia o plata in numele altui utilizator.';
    end if;
  end if;

  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat pentru a trimite bani.';
  end if;

  -- ---------------------------------------------------------------------------
  -- Validari de intrare
  -- ---------------------------------------------------------------------------
  if p_suma is null or p_suma <= 0 then
    raise exception 'SUMA_INVALIDA'
      using detail = 'Suma trebuie sa fie mai mare decat 0.';
  end if;

  if round(p_suma, 2) <> p_suma then
    raise exception 'SUMA_INVALIDA'
      using detail = 'Suma poate avea cel mult doua zecimale.';
  end if;

  v_suma := round(p_suma, 2);

  v_iban := nullif(upper(regexp_replace(coalesce(p_iban_dest, ''), '\s', '', 'g')), '');

  if v_iban is null or v_iban !~ '^RO[0-9]{2}[A-Z0-9]{20}$' then
    raise exception 'IBAN_INVALID'
      using detail = 'IBAN-ul beneficiarului este invalid.';
  end if;

  -- ---------------------------------------------------------------------------
  -- Contul sursa: cel cerut, altfel contul cel mai vechi al utilizatorului
  -- ---------------------------------------------------------------------------
  if p_id_cont_send is not null then
    select c.id into v_id_send
      from public.conturi_bancare c
     where c.id = p_id_cont_send
       and c.id_user = v_user;

    if v_id_send is null then
      -- Nu spunem daca contul lipseste sau e al altcuiva doar dupa id: verificam
      -- separat, ca mesajul sa fie util fara sa dezvaluie conturi straine.
      if exists (select 1 from public.conturi_bancare c where c.id = p_id_cont_send) then
        raise exception 'CONT_SURSA_STRAIN'
          using detail = 'Nu poti plati dintr-un cont care nu este al tau.';
      end if;

      raise exception 'CONT_SURSA_INEXISTENT'
        using detail = 'Contul din care vrei sa platesti nu exista.';
    end if;
  else
    select c.id into v_id_send
      from public.conturi_bancare c
     where c.id_user = v_user
     order by c.creat_la, c.id
     limit 1;

    if v_id_send is null then
      raise exception 'CONT_SURSA_INEXISTENT'
        using detail = 'Nu ai niciun cont din care sa platesti.';
    end if;
  end if;

  -- ---------------------------------------------------------------------------
  -- Contul beneficiar, dupa IBAN
  -- ---------------------------------------------------------------------------
  select c.id into v_id_recv
    from public.conturi_bancare c
   where c.iban = v_iban;

  if v_id_recv is null then
    raise exception 'BENEFICIAR_INEXISTENT'
      using detail = 'Nu exista niciun cont Libra cu acest IBAN.';
  end if;

  -- Intre doua conturi proprii se poate; in acelasi cont, nu.
  if v_id_recv = v_id_send then
    raise exception 'AUTOTRANSFER'
      using detail = 'Nu poti trimite bani in acelasi cont din care platesti.';
  end if;

  -- Blocam randurile in ordinea id-ului, in doua instructiuni separate.
  -- „order by ... for update" NU garanteaza ordinea blocarii (randurile se
  -- blocheaza pe masura ce ies din scan, inainte de sortare), deci doua
  -- transferuri incrucisate A->B si B->A s-ar putea bloca reciproc. Doua
  -- comenzi explicite, mereu in aceeasi ordine, elimina deadlock-ul.
  if v_id_send < v_id_recv then
    perform 1 from public.conturi_bancare c where c.id = v_id_send for update;
    perform 1 from public.conturi_bancare c where c.id = v_id_recv for update;
  else
    perform 1 from public.conturi_bancare c where c.id = v_id_recv for update;
    perform 1 from public.conturi_bancare c where c.id = v_id_send for update;
  end if;

  -- Citim soldurile abia sub lock: intre verificari si lock se putea strecura
  -- alt transfer din acelasi cont.
  select * into v_send from public.conturi_bancare c where c.id = v_id_send;
  select * into v_recv from public.conturi_bancare c where c.id = v_id_recv;

  -- Suma se da in valuta contului sursa. Daca apelantul trimite totusi p_valuta,
  -- trebuie sa fie aceeasi — altfel nu se stie ce a vrut sa spuna.
  if p_valuta is not null and upper(btrim(p_valuta)) <> v_send.valuta then
    raise exception 'VALUTA_NESUPORTATA'
      using detail = format('Contul sursa e in %s; suma se da in aceeasi valuta.', v_send.valuta);
  end if;

  -- ---------------------------------------------------------------------------
  -- Fonduri
  -- ---------------------------------------------------------------------------
  if v_send.sold < v_suma then
    raise exception 'FONDURI_INSUFICIENTE'
      using detail = format('Sold disponibil: %s %s, suma ceruta: %s %s.',
                            v_send.sold, v_send.valuta, v_suma, v_send.valuta);
  end if;

  -- Cat ajunge efectiv in contul beneficiarului, in valuta LUI.
  v_primit := public.converteste(v_suma, v_send.valuta, v_recv.valuta);

  if v_primit <= 0 then
    raise exception 'SUMA_PREA_MICA'
      using detail = 'Suma e prea mica pentru a ajunge in valuta beneficiarului.';
  end if;

  -- ---------------------------------------------------------------------------
  -- Miscarea banilor + istoric (totul in aceeasi tranzactie)
  -- ---------------------------------------------------------------------------
  update public.conturi_bancare
     set sold = sold - v_suma
   where id = v_send.id
   returning * into v_send;

  update public.conturi_bancare
     set sold = sold + v_primit
   where id = v_recv.id
   returning * into v_recv;

  -- Tranzactia se scrie in valuta in care a fost initiata, adica a sursei.
  insert into public.tranzactii (
    id_user_send, id_user_recieve, id_cont_send, id_cont_recieve,
    suma, valuta, descriere
  )
  values (
    v_send.id_user, v_recv.id_user, v_send.id, v_recv.id,
    v_suma, v_send.valuta, nullif(btrim(coalesce(p_descriere, '')), '')
  )
  returning * into v_tranz;

  select p.nume into v_nume_recv
    from public.profiles p
   where p.id = v_recv.id_user;

  return jsonb_build_object(
    'id_tranzactie',   v_tranz.id,
    'suma',            v_tranz.suma,
    'valuta',          v_tranz.valuta,
    'suma_primita',    v_primit,
    'valuta_primita',  v_recv.valuta,
    'creat_la',        v_tranz.creat_la,
    'id_cont_send',    v_send.id,
    'sold_nou',        v_send.sold,
    'id_cont_recieve', v_recv.id,
    'id_user_recieve', v_recv.id_user,
    'beneficiar',      v_nume_recv,
    'iban_mascat',     '**** ' || right(v_recv.iban, 4)
  );
end;
$function$
;
CREATE OR REPLACE FUNCTION public.core_banking_groups(p_id_group bigint, p_suma numeric, p_directie text DEFAULT 'depunere'::text, p_descriere text DEFAULT NULL::text, p_id_cont uuid DEFAULT NULL::uuid, p_iban_dest text DEFAULT NULL::text, p_valuta text DEFAULT NULL::text, p_id_user uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_user      uuid;
  -- service_role, sau o sesiune SQL directa (fara JWT, deci deja privilegiata).
  v_este_srv  boolean := coalesce(auth.role(), 'service_role') = 'service_role';
  v_directie  text := lower(btrim(coalesce(p_directie, 'depunere')));
  v_suma      numeric(14,2);
  v_in_grup   numeric(14,2);
  v_in_cont   numeric(14,2);
  v_iban      text;
  v_id_cont   uuid;
  v_cont      public.conturi_bancare%rowtype;
  v_grup      public.groups%rowtype;
  v_nume_cont text;
  v_nume_send text;
  v_valuta_sursa text;
  v_tranz     public.tranzactii%rowtype;
begin
  -- ---------------------------------------------------------------------------
  -- Cine misca banii
  -- ---------------------------------------------------------------------------
  if v_este_srv then
    v_user := coalesce(p_id_user, auth.uid());
  else
    v_user := auth.uid();

    if p_id_user is not null and p_id_user <> v_user then
      raise exception 'NEAUTORIZAT'
        using detail = 'Nu poti misca bani in numele altui utilizator.';
    end if;
  end if;

  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat.';
  end if;

  -- ---------------------------------------------------------------------------
  -- Validari de intrare
  -- ---------------------------------------------------------------------------
  if v_directie not in ('depunere', 'plata') then
    raise exception 'DIRECTIE_INVALIDA'
      using detail = 'Directia poate fi doar „depunere" sau „plata".';
  end if;

  if p_suma is null or p_suma <= 0 then
    raise exception 'SUMA_INVALIDA'
      using detail = 'Suma trebuie sa fie mai mare decat 0.';
  end if;

  if round(p_suma, 2) <> p_suma then
    raise exception 'SUMA_INVALIDA'
      using detail = 'Suma poate avea cel mult doua zecimale.';
  end if;

  v_suma := round(p_suma, 2);

  -- ---------------------------------------------------------------------------
  -- Grupul: trebuie sa existe si sa fii membru in el
  -- ---------------------------------------------------------------------------
  select * into v_grup from public.groups g where g.id = p_id_group;

  if not found then
    raise exception 'GRUP_INEXISTENT'
      using detail = 'Grupul nu exista.';
  end if;

  -- Verificarea se face pe v_user, nu pe auth.uid(): asa merge si cand apelul
  -- vine din backend cu service_role, pentru un utilizator anume.
  if not exists (
    select 1 from public.groups_participants gp
     where gp.id_group = v_grup.id and gp.id_user = v_user
  ) then
    raise exception 'NU_ESTI_MEMBRU'
      using detail = 'Nu faci parte din acest grup.';
  end if;

  -- ---------------------------------------------------------------------------
  -- Contul de la celalalt capat
  -- ---------------------------------------------------------------------------
  if v_directie = 'depunere' then
    -- Contul sursa: cel cerut, altfel cel mai vechi cont al utilizatorului.
    if p_id_cont is not null then
      select c.id into v_id_cont
        from public.conturi_bancare c
       where c.id = p_id_cont
         and c.id_user = v_user;

      if v_id_cont is null then
        if exists (select 1 from public.conturi_bancare c where c.id = p_id_cont) then
          raise exception 'CONT_SURSA_STRAIN'
            using detail = 'Nu poti pune bani in grup dintr-un cont care nu e al tau.';
        end if;

        raise exception 'CONT_SURSA_INEXISTENT'
          using detail = 'Contul din care vrei sa platesti nu exista.';
      end if;
    else
      select c.id into v_id_cont
        from public.conturi_bancare c
       where c.id_user = v_user
       order by c.creat_la, c.id
       limit 1;

      if v_id_cont is null then
        raise exception 'CONT_SURSA_INEXISTENT'
          using detail = 'Nu ai niciun cont din care sa pui bani.';
      end if;
    end if;
  else
    -- Plata: contul destinatie se identifica prin IBAN, ca la core_banking.
    v_iban := nullif(upper(regexp_replace(coalesce(p_iban_dest, ''), '\s', '', 'g')), '');

    if v_iban is null or v_iban !~ '^RO[0-9]{2}[A-Z0-9]{20}$' then
      raise exception 'IBAN_INVALID'
        using detail = 'IBAN-ul beneficiarului este invalid.';
    end if;

    select c.id into v_id_cont
      from public.conturi_bancare c
     where c.iban = v_iban;

    if v_id_cont is null then
      raise exception 'BENEFICIAR_INEXISTENT'
        using detail = 'Nu exista niciun cont Libra cu acest IBAN.';
    end if;
  end if;

  -- ---------------------------------------------------------------------------
  -- Lock: intai contul, apoi grupul. Mereu in ordinea asta, in ambele directii.
  -- ---------------------------------------------------------------------------
  perform 1 from public.conturi_bancare c where c.id = v_id_cont for update;
  perform 1 from public.groups         g where g.id = v_grup.id  for update;

  -- Soldurile se citesc abia sub lock: pana aici se putea strecura alta plata.
  select * into v_cont from public.conturi_bancare c where c.id = v_id_cont;
  select * into v_grup from public.groups         g where g.id = v_grup.id;

  -- Sursa e contul la depunere si grupul (mereu RON) la plata.
  v_valuta_sursa := case when v_directie = 'depunere' then v_cont.valuta else 'RON' end;

  if p_valuta is not null and upper(btrim(p_valuta)) <> v_valuta_sursa then
    raise exception 'VALUTA_NESUPORTATA'
      using detail = format('Suma se da in %s, valuta sursei.', v_valuta_sursa);
  end if;

  -- Numele autorului, pentru textul anuntului din conversatie. Se ia o singura
  -- data, ambele ramuri scriu cate un mesaj.
  select p.nume into v_nume_send from public.profiles p where p.id = v_user;

  -- ---------------------------------------------------------------------------
  -- Miscarea banilor + istoric (totul in aceeasi tranzactie)
  -- ---------------------------------------------------------------------------
  if v_directie = 'depunere' then
    if v_cont.sold < v_suma then
      raise exception 'FONDURI_INSUFICIENTE'
        using detail = format('Sold disponibil: %s %s, suma ceruta: %s %s.',
                              v_cont.sold, v_cont.valuta, v_suma, v_cont.valuta);
    end if;

    -- In punga comuna intra echivalentul in RON.
    v_in_grup := public.converteste(v_suma, v_cont.valuta, 'RON');

    if v_in_grup <= 0 then
      raise exception 'SUMA_PREA_MICA'
        using detail = 'Suma e prea mica pentru a ajunge in soldul grupului.';
    end if;

    update public.conturi_bancare set sold = sold - v_suma
     where id = v_cont.id
     returning * into v_cont;

    update public.groups set sold = sold + v_in_grup
     where id = v_grup.id
     returning * into v_grup;

    -- Beneficiarul e grupul, nu o persoana: id_user_recieve ramane null.
    insert into public.tranzactii (
      id_user_send, id_cont_send, id_group_recieve, suma, valuta, descriere
    )
    values (
      v_user, v_cont.id, v_grup.id, v_suma, v_cont.valuta,
      nullif(btrim(coalesce(p_descriere, '')), '')
    )
    returning * into v_tranz;

    -- Anuntul din conversatie. Suma e cea care a intrat efectiv in grup, in RON:
    -- ceilalti membri vad cifra care le schimba soldul comun, nu ce a scos
    -- expeditorul din contul lui valutar.
    insert into public.group_messages (continut, id_user, id_group, type)
    values (
      format('%s a pus %s RON în grup.',
             coalesce(v_nume_send, 'Un membru'),
             public.formateaza_suma_ron(v_in_grup)),
      v_user,
      v_grup.id,
      'incasare'
    );
  else
    if v_grup.sold < v_suma then
      raise exception 'FONDURI_INSUFICIENTE_GRUP'
        using detail = format('Soldul grupului: %s RON, suma ceruta: %s RON.',
                              v_grup.sold, v_suma);
    end if;

    -- Din grup pleaca RON, in contul beneficiarului intra valuta lui.
    v_in_cont := public.converteste(v_suma, 'RON', v_cont.valuta);

    if v_in_cont <= 0 then
      raise exception 'SUMA_PREA_MICA'
        using detail = 'Suma e prea mica pentru a ajunge in valuta beneficiarului.';
    end if;

    update public.groups set sold = sold - v_suma
     where id = v_grup.id
     returning * into v_grup;

    update public.conturi_bancare set sold = sold + v_in_cont
     where id = v_cont.id
     returning * into v_cont;

    -- Expeditorul-persoana ramane cel care a apasat butonul (audit), dar banii
    -- au plecat din grup: id_cont_send e null, id_group_send arata sursa reala.
    insert into public.tranzactii (
      id_user_send, id_group_send, id_user_recieve, id_cont_recieve,
      suma, valuta, descriere
    )
    values (
      v_user, v_grup.id, v_cont.id_user, v_cont.id,
      v_suma, 'RON', nullif(btrim(coalesce(p_descriere, '')), '')
    )
    returning * into v_tranz;

    -- Perechea anuntului de incasare. Nu spunem si unde s-au dus banii:
    -- IBAN-ul si titularul sunt treaba istoricului, nu a conversatiei — in grup
    -- conteaza ca soldul comun a scazut si cine a decis asta.
    insert into public.group_messages (continut, id_user, id_group, type)
    values (
      format('%s a scos %s RON din grup.',
             coalesce(v_nume_send, 'Un membru'),
             public.formateaza_suma_ron(v_suma)),
      v_user,
      v_grup.id,
      'plata'
    );
  end if;

  select p.nume into v_nume_cont
    from public.profiles p
   where p.id = v_cont.id_user;

  return jsonb_build_object(
    'id_tranzactie', v_tranz.id,
    'directie',      v_directie,
    'suma',          v_tranz.suma,
    'valuta',        v_tranz.valuta,
    'creat_la',      v_tranz.creat_la,
    'id_group',      v_grup.id,
    'nume_grup',     v_grup.nume,
    'sold_grup',     v_grup.sold,
    'id_cont',       v_cont.id,
    'sold_cont',     v_cont.sold,
    'valuta_cont',   v_cont.valuta,
    'titular_cont',  v_nume_cont,
    'iban_mascat',   '**** ' || right(v_cont.iban, 4)
  );
end;
$function$
;
CREATE OR REPLACE FUNCTION public.creeaza_cont_initial()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  insert into public.conturi_bancare (id_user, nume, iban)
  values (new.id, 'Cont curent', new.iban_cont)
  on conflict (iban) do nothing;

  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.creeaza_grup(p_nume text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_max_grupuri constant integer := 30;
  v_user  uuid := auth.uid();
  v_nume  text := nullif(btrim(coalesce(p_nume, '')), '');
  v_grup  public.groups%rowtype;
  v_cate  integer;
begin
  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat ca sa creezi un grup.';
  end if;

  if v_nume is null or char_length(v_nume) < 2 or char_length(v_nume) > 60 then
    raise exception 'NUME_INVALID'
      using detail = 'Numele grupului trebuie sa aiba intre 2 si 60 de caractere.';
  end if;

  select count(*) into v_cate
    from public.groups_participants gp
   where gp.id_user = v_user;

  if v_cate >= v_max_grupuri then
    raise exception 'PREA_MULTE_GRUPURI'
      using detail = format('Poti face parte din cel mult %s grupuri.', v_max_grupuri);
  end if;

  insert into public.groups (nume, token_acces, id_creator)
  values (v_nume, public.genereaza_token_grup(), v_user)
  returning * into v_grup;

  insert into public.groups_participants (id_user, id_group)
  values (v_user, v_grup.id);

  return jsonb_build_object(
    'id',          v_grup.id,
    'nume',        v_grup.nume,
    'token_acces', v_grup.token_acces,
    'sold',        v_grup.sold
  );
end;
$function$
;
CREATE OR REPLACE FUNCTION public.creeaza_plata(p_id_user uuid, p_numar_card text, p_data_expirare text, p_ccv text, p_suma numeric, p_comerciant text, p_descriere text DEFAULT NULL::text, p_valuta text DEFAULT 'RON'::text, p_secunde integer DEFAULT 120)
 RETURNS payments
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
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
$function$
;
CREATE OR REPLACE FUNCTION public.curs_ron(p_valuta text)
 RETURNS numeric
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_curs numeric;
begin
  select c.curs into v_curs
    from public.curs_valutar c
   where c.valuta = p_valuta;

  if v_curs is null then
    raise exception 'CURS_INDISPONIBIL'
      using detail = format('Nu am cursul pentru %s.', p_valuta);
  end if;

  return v_curs;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.enforce_user_identity_immutability()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
begin
  if new.id <> old.id
     or new.cnp <> old.cnp
     or new.data_nasterii is distinct from old.data_nasterii then
    raise exception 'Columns id, cnp and data_nasterii are immutable on public."user"'
      using errcode = '42501';
  end if;

  new.created_at := old.created_at;
  new.updated_at := now();
  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.este_membru_grup(p_id_group bigint)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select exists (
    select 1
      from public.groups_participants gp
     where gp.id_group = p_id_group
       and gp.id_user  = auth.uid()
  );
$function$
;
CREATE OR REPLACE FUNCTION public.formateaza_suma_ron(p_suma numeric)
 RETURNS text
 LANGUAGE sql
 IMMUTABLE
 SET search_path TO ''
AS $function$
  -- Masca foloseste ',' si '.' literale, nu G si D — acelea depind de lc_numeric
  -- al serverului, care pe Supabase e englezesc. Rezulta '1,250.50', iar
  -- translate schimba intre ele cele doua semne: '1.250,50'.
  select translate(to_char(p_suma, 'FM999,999,999,990.00'), ',.', '.,');
$function$
;
CREATE OR REPLACE FUNCTION public.genereaza_iban()
 RETURNS text
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
declare
  v_banca text := 'LIBR';
  v_cont  text;
  v_control integer;
  i integer;
begin
  for i in 1..40 loop
    v_cont := lpad(floor(random() * 1e16)::bigint::text, 16, '0');

    v_control := 98 - public.iban_mod97(
      public.iban_litere_in_cifre(v_banca || v_cont || 'RO00')
    );

    v_cont := 'RO' || lpad(v_control::text, 2, '0') || v_banca || v_cont;

    -- Unic si intre conturi, si fata de IBAN-urile istorice de pe profiluri.
    if not exists (select 1 from public.conturi_bancare c where c.iban = v_cont)
       and not exists (select 1 from public.profiles p where p.iban_cont = v_cont) then
      return v_cont;
    end if;
  end loop;

  raise exception 'Nu s-a putut genera un IBAN unic.';
end;
$function$
;
CREATE OR REPLACE FUNCTION public.genereaza_token_grup()
 RETURNS text
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
declare
  v_alfabet constant text := 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';  -- fara I, L, O, 0, 1
  v_hex   text;
  v_token text;
  i integer;
  j integer;
begin
  for i in 1..40 loop
    v_hex   := replace(gen_random_uuid()::text, '-', '');
    v_token := '';

    for j in 1..12 loop
      v_token := v_token || substr(
        v_alfabet,
        1 + (('x' || substr(v_hex, j * 2 - 1, 2))::bit(8)::integer % 31),
        1
      );
    end loop;

    if not exists (select 1 from public.groups g where g.token_acces = v_token) then
      return v_token;
    end if;
  end loop;

  raise exception 'Nu s-a putut genera un token unic de grup.';
end;
$function$
;
CREATE OR REPLACE FUNCTION public.groups_modificat_la()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
begin
  new.id          := old.id;
  new.token_acces := old.token_acces;
  new.creat_la    := old.creat_la;
  new.modificat_la := now();
  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.grup_dupa_token(p_token text)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_token text := nullif(btrim(upper(coalesce(p_token, ''))), '');
  v_grup  public.groups%rowtype;
begin
  if auth.uid() is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat.';
  end if;

  if v_token is null or v_token !~ '^[A-HJKMNP-Z2-9]{12}$' then
    raise exception 'TOKEN_INVALID'
      using detail = 'Codul grupului este invalid.';
  end if;

  select * into v_grup from public.groups g where g.token_acces = v_token;

  if not found then
    raise exception 'GRUP_INEXISTENT'
      using detail = 'Nu exista niciun grup cu acest cod.';
  end if;

  return jsonb_build_object(
    'id',        v_grup.id,
    'nume',      v_grup.nume,
    'membri',    (select count(*) from public.groups_participants gp where gp.id_group = v_grup.id),
    'sunt_deja', public.este_membru_grup(v_grup.id)
  );
end;
$function$
;
CREATE OR REPLACE FUNCTION public.handle_new_user()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_meta      jsonb := coalesce(new.raw_user_meta_data, '{}'::jsonb);
  v_nume      text  := nullif(btrim(v_meta ->> 'nume'), '');
  v_cnp       text  := nullif(btrim(v_meta ->> 'cnp'), '');
  v_telefon   text  := nullif(btrim(v_meta ->> 'telefon'), '');
  v_iban      text  := nullif(btrim(upper(v_meta ->> 'iban_cont')), '');
begin
  if v_nume is null then
    raise exception 'Lipseste "nume" din user_metadata.' using errcode = '23514';
  end if;

  if v_cnp is null then
    raise exception 'Lipseste "cnp" din user_metadata.' using errcode = '23514';
  end if;

  if v_telefon is null then
    raise exception 'Lipseste "telefon" din user_metadata.' using errcode = '23514';
  end if;

  -- Normalizare telefon: 07xx xxx xxx -> +407xxxxxxxx
  v_telefon := regexp_replace(v_telefon, '[^0-9+]', '', 'g');
  if v_telefon ~ '^0[0-9]{9}$' then
    v_telefon := '+4' || v_telefon;
  elsif v_telefon ~ '^40[0-9]{9}$' then
    v_telefon := '+' || v_telefon;
  end if;

  -- IBAN-ul vine din metadata; daca lipseste, il generam aici.
  if v_iban is null then
    v_iban := public.genereaza_iban();
  end if;

  insert into public.profiles (id, nume, cnp, telefon, email, iban_cont)
  values (new.id, v_nume, v_cnp, v_telefon, new.email, v_iban);

  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.handle_user_email_update()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if new.email is distinct from old.email then
    update public.profiles
       set email = new.email,
           modificat_la = now()
     where id = new.id;
  end if;

  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.iban_litere_in_cifre(p_text text)
 RETURNS text
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO ''
AS $function$
declare
  v_out text := '';
  v_ch  text;
  i integer;
begin
  for i in 1..char_length(p_text) loop
    v_ch := substr(upper(p_text), i, 1);
    if v_ch ~ '[0-9]' then
      v_out := v_out || v_ch;
    elsif v_ch ~ '[A-Z]' then
      v_out := v_out || (ascii(v_ch) - 55)::text;
    else
      raise exception 'Caracter invalid in IBAN: %', v_ch;
    end if;
  end loop;

  return v_out;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.iban_mod97(p_digits text)
 RETURNS integer
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO ''
AS $function$
declare
  v_rest text := '';
  v_bucata text;
  i integer := 1;
begin
  while i <= char_length(p_digits) loop
    v_bucata := v_rest || substr(p_digits, i, 7);
    v_rest   := (v_bucata::bigint % 97)::text;
    i := i + 7;
  end loop;

  return v_rest::integer;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.intra_in_grup(p_token text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_max_grupuri constant integer := 30;
  v_user  uuid := auth.uid();
  v_token text := nullif(btrim(upper(coalesce(p_token, ''))), '');
  v_grup  public.groups%rowtype;
  v_cate  integer;
begin
  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat ca sa intri intr-un grup.';
  end if;

  if v_token is null or v_token !~ '^[A-HJKMNP-Z2-9]{12}$' then
    raise exception 'TOKEN_INVALID'
      using detail = 'Codul grupului este invalid.';
  end if;

  select * into v_grup from public.groups g where g.token_acces = v_token;

  if not found then
    raise exception 'GRUP_INEXISTENT'
      using detail = 'Nu exista niciun grup cu acest cod.';
  end if;

  -- Plafonul nu se aplica daca esti deja inauntru: reintrarea pe acelasi link
  -- nu trebuie sa dea eroare.
  if not public.este_membru_grup(v_grup.id) then
    select count(*) into v_cate
      from public.groups_participants gp
     where gp.id_user = v_user;

    if v_cate >= v_max_grupuri then
      raise exception 'PREA_MULTE_GRUPURI'
        using detail = format('Poti face parte din cel mult %s grupuri.', v_max_grupuri);
    end if;

    insert into public.groups_participants (id_user, id_group)
    values (v_user, v_grup.id)
    on conflict (id_group, id_user) do nothing;
  end if;

  return jsonb_build_object(
    'id',   v_grup.id,
    'nume', v_grup.nume,
    'sold', v_grup.sold
  );
end;
$function$
;
CREATE OR REPLACE FUNCTION public.is_valid_cnp(p_cnp text)
 RETURNS boolean
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO ''
AS $function$
declare
  control_key constant text := '279146358279';
  total       integer := 0;
  control     integer;
  gender      integer;
  county      integer;
  century     integer;
  i           integer;
begin
  if p_cnp is null or p_cnp !~ '^[1-9][0-9]{12}$' then
    return false;
  end if;

  for i in 1..12 loop
    total := total + substr(p_cnp, i, 1)::integer * substr(control_key, i, 1)::integer;
  end loop;

  control := total % 11;
  if control = 10 then
    control := 1;
  end if;
  if control <> substr(p_cnp, 13, 1)::integer then
    return false;
  end if;

  county := substr(p_cnp, 8, 2)::integer;
  if county not between 1 and 46 and county not in (51, 52, 70) then
    return false;
  end if;

  gender := substr(p_cnp, 1, 1)::integer;
  century := case
    when gender in (1, 2) then 1900
    when gender in (3, 4) then 1800
    when gender in (5, 6) then 2000
    else null                       -- residents (7, 8) and foreigners (9)
  end;                              -- do not encode the century

  if century is not null then
    begin
      perform make_date(
        century + substr(p_cnp, 2, 2)::integer,
        substr(p_cnp, 4, 2)::integer,
        substr(p_cnp, 6, 2)::integer
      );
    exception
      when others then
        return false;
    end;
  end if;

  return true;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.match_knowledge_chunks(p_embedding_key text, p_query_embedding vector, p_languages text[] DEFAULT NULL::text[], p_document_types text[] DEFAULT NULL::text[], p_audience text DEFAULT 'customer'::text, p_match_count integer DEFAULT 6, p_min_score double precision DEFAULT 0.5)
 RETURNS TABLE(chunk_id text, document_id text, versiune integer, sectiune text, continut text, metadata jsonb, scor double precision)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public'
AS $function$
  select
    kc.chunk_id,
    kc.document_id,
    kc.versiune,
    kc.sectiune,
    kc.continut,
    kc.metadata,
    1 - (kc.embedding <=> p_query_embedding) as scor
  from public.knowledge_chunks kc
  join public.knowledge_documents kd
    on kd.document_id = kc.document_id and kd.versiune = kc.versiune
  where kc.embedding_key = p_embedding_key
    and kd.audienta in ('customer', p_audience)
    and (p_languages is null or kd.limba = any (p_languages))
    and (p_document_types is null or kd.tip_document = any (p_document_types))
    and (1 - (kc.embedding <=> p_query_embedding)) >= p_min_score
  order by kc.embedding <=> p_query_embedding
  limit greatest(p_match_count, 0);
$function$
;
CREATE OR REPLACE FUNCTION public.membri_grup(p_id_group bigint)
 RETURNS TABLE(id_user uuid, nume text, avatar_url text, creat_la timestamp with time zone)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select gp.id_user, p.nume, p.avatar_url, gp.creat_la
    from public.groups_participants gp
    join public.profiles p on p.id = gp.id_user
   where gp.id_group = p_id_group
     and public.este_membru_grup(p_id_group)   -- doar membrii vad lista
   order by gp.creat_la, gp.id;
$function$
;
CREATE OR REPLACE FUNCTION public.plata_finalizeaza(p_id uuid, p_status text, p_motiv text DEFAULT NULL::text)
 RETURNS payments
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
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
$function$
;
CREATE OR REPLACE FUNCTION public.profiles_protejeaza_campuri()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
begin
  -- CNP-ul, IBAN-ul si id-ul nu se schimba din aplicatie.
  new.id        := old.id;
  new.cnp       := old.cnp;
  new.iban_cont := old.iban_cont;
  new.creat_la  := old.creat_la;
  new.modificat_la := now();

  -- Soldul nu se schimba din client — altfel oricine si-ar putea seta oricat,
  -- avand politica de update pe propriul profil (0001_profiles.sql).
  if auth.role() <> 'service_role'
     and coalesce(current_setting('app.core_banking', true), 'off') <> 'on' then
    new.sold_curent := old.sold_curent;
  end if;

  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.respinge_plata(p_id uuid, p_id_user uuid)
 RETURNS payments
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
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
$function$
;
CREATE OR REPLACE FUNCTION public.rls_auto_enable()
 RETURNS event_trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog'
AS $function$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
      AND object_type IN ('table','partitioned table')
  LOOP
     IF cmd.schema_name IS NOT NULL AND cmd.schema_name IN ('public') AND cmd.schema_name NOT IN ('pg_catalog','information_schema') AND cmd.schema_name NOT LIKE 'pg_toast%' AND cmd.schema_name NOT LIKE 'pg_temp%' THEN
      BEGIN
        EXECUTE format('alter table if exists %s enable row level security', cmd.object_identity);
        RAISE LOG 'rls_auto_enable: enabled RLS on %', cmd.object_identity;
      EXCEPTION
        WHEN OTHERS THEN
          RAISE LOG 'rls_auto_enable: failed to enable RLS on %', cmd.object_identity;
      END;
     ELSE
        RAISE LOG 'rls_auto_enable: skip % (either system schema or not in enforced list: %.)', cmd.object_identity, cmd.schema_name;
     END IF;
  END LOOP;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.schimba_valuta_cont(p_id_cont uuid, p_valuta_noua text, p_id_user uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_user      uuid;
  v_este_srv  boolean := coalesce(auth.role(), 'service_role') = 'service_role';
  v_valuta    text := upper(btrim(coalesce(p_valuta_noua, '')));
  v_cont      public.conturi_bancare%rowtype;
  v_sold_vechi numeric(14,2);
  v_valuta_veche text;
  v_sold_nou  numeric(14,2);
begin
  -- ---------------------------------------------------------------------------
  -- Cine schimba
  -- ---------------------------------------------------------------------------
  if v_este_srv then
    v_user := coalesce(p_id_user, auth.uid());
  else
    v_user := auth.uid();

    if p_id_user is not null and p_id_user <> v_user then
      raise exception 'NEAUTORIZAT'
        using detail = 'Nu poti schimba valuta unui cont in numele altcuiva.';
    end if;
  end if;

  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat.';
  end if;

  if v_valuta not in ('RON', 'EUR', 'USD', 'GBP', 'CHF') then
    raise exception 'VALUTA_NESUPORTATA'
      using detail = 'Se poate schimba doar in RON, EUR, USD, GBP sau CHF.';
  end if;

  -- ---------------------------------------------------------------------------
  -- Contul trebuie sa fie al tau
  -- ---------------------------------------------------------------------------
  select c.id into v_cont.id
    from public.conturi_bancare c
   where c.id = p_id_cont
     and c.id_user = v_user;

  if v_cont.id is null then
    if exists (select 1 from public.conturi_bancare c where c.id = p_id_cont) then
      raise exception 'CONT_STRAIN'
        using detail = 'Nu poti schimba valuta unui cont care nu e al tau.';
    end if;

    raise exception 'CONT_INEXISTENT'
      using detail = 'Contul nu exista.';
  end if;

  -- Soldul se citeste abia sub lock: intre verificare si schimb se putea
  -- strecura un transfer din acelasi cont, si am fi convertit o cifra veche.
  perform 1 from public.conturi_bancare c where c.id = v_cont.id for update;
  select * into v_cont from public.conturi_bancare c where c.id = v_cont.id;

  if v_cont.valuta = v_valuta then
    raise exception 'ACEEASI_VALUTA'
      using detail = 'Contul e deja in aceasta valuta.';
  end if;

  v_sold_vechi   := v_cont.sold;
  v_valuta_veche := v_cont.valuta;
  v_sold_nou     := public.converteste(v_sold_vechi, v_valuta_veche, v_valuta);

  -- Un sold mic intr-o valuta scumpa se poate rotunji la zero. Mai bine oprim
  -- decat sa stergem banii omului la rotunjire.
  if v_sold_vechi > 0 and v_sold_nou <= 0 then
    raise exception 'SUMA_PREA_MICA'
      using detail = 'Soldul e prea mic pentru a fi convertit in aceasta valuta.';
  end if;

  update public.conturi_bancare
     set sold = v_sold_nou,
         valuta = v_valuta
   where id = v_cont.id
   returning * into v_cont;

  return jsonb_build_object(
    'id_cont',      v_cont.id,
    'valuta_veche', v_valuta_veche,
    'sold_vechi',   v_sold_vechi,
    'valuta',       v_cont.valuta,
    'sold',         v_cont.sold,
    'curs',         public.curs_ron(v_valuta_veche) / public.curs_ron(v_valuta)
  );
end;
$function$
;
CREATE OR REPLACE FUNCTION public.sync_user_email()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if new.email is distinct from old.email then
    update public."user" set email = new.email where id = new.id;
  end if;
  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.sync_verification_status()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  update public.profiles
     set verification_status = new.status,
         modificat_la = now()
   where id = new.id_user;

  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.tranzactii_anunta_realtime()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_send      uuid := new.id_user_send;
  v_recv      uuid := new.id_user_recieve;
  v_nume_send text;
  v_nume_recv text;
  v_grup_send text;
  v_grup_recv text;
  v_suma_text text;
begin
  -- Tot corpul e la adapost: niciun SELECT de aici nu are voie sa anuleze
  -- transferul care tocmai a reusit.
  begin
    -- Numele se citesc cu drepturile proprietarului functiei, deci RLS de pe
    -- profiles (doar randul propriu, 0001) nu incurca — acelasi tipar ca in
    -- core_banking_groups, 0010_mesaje_incasare.sql.
    select p.nume into v_nume_send from public.profiles p where p.id = v_send;
    select p.nume into v_nume_recv from public.profiles p where p.id = v_recv;

    if new.id_group_send is not null then
      select g.nume into v_grup_send from public.groups g where g.id = new.id_group_send;
    end if;

    if new.id_group_recieve is not null then
      select g.nume into v_grup_recv from public.groups g where g.id = new.id_group_recieve;
    end if;

    -- '250,00', ca in mesajele de sistem din grupuri (0010).
    v_suma_text := public.formateaza_suma_ron(new.suma);

    -- Expeditorul
    if v_send is not null then
      perform public.anunta_utilizator(v_send, 'tranzactie', jsonb_build_object(
        'id',          new.id,
        'suma',        new.suma,
        'suma_text',   v_suma_text,
        'valuta',      new.valuta,
        'descriere',   new.descriere,
        'creat_la',    new.creat_la,
        'directie',    case
                         when v_recv is not distinct from v_send
                              and new.id_group_send is null
                              and new.id_group_recieve is null
                         then 'proprie'
                         else 'trimisa'
                       end,
        'contraparte', coalesce(v_grup_recv, v_nume_recv),
        'notifica',    false
      ));
    end if;

    -- Beneficiarul. „is distinct from" acopera si null-ul: la o depunere in
    -- grup nu exista beneficiar-persoana, deci nu se trimite nimic aici.
    if v_recv is not null and v_recv is distinct from v_send then
      perform public.anunta_utilizator(v_recv, 'tranzactie', jsonb_build_object(
        'id',          new.id,
        'suma',        new.suma,
        'suma_text',   v_suma_text,
        'valuta',      new.valuta,
        'descriere',   new.descriere,
        'creat_la',    new.creat_la,
        'directie',    'primita',
        'contraparte', coalesce(v_grup_send, v_nume_send),
        'notifica',    true
      ));
    end if;
  exception when others then
    raise warning 'REALTIME_TRANZACTIE_ESUAT (id=%): %', new.id, sqlerrm;
  end;

  return null;  -- trigger AFTER: valoarea intoarsa se ignora
end;
$function$
;
-- agent_runs               id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- agent_runs               id_user                      uuid                           
-- agent_runs               id_conversation              uuid                           
-- agent_runs               id_agent                     text                           NOT NULL 
-- agent_runs               intentie                     text                           
-- agent_runs               nivel_risc                   text                           
-- agent_runs               versiune_prompt              text                           
-- agent_runs               deployment                   text                           
-- agent_runs               latenta_ms                   integer                        
-- agent_runs               numar_tool_uri               integer                        NOT NULL DEFAULT 0
-- agent_runs               fragmente_regasite           integer                        NOT NULL DEFAULT 0
-- agent_runs               context_caractere            integer                        
-- agent_runs               succes                       boolean                        NOT NULL 
-- agent_runs               cod_eroare                   text                           
-- agent_runs               creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- ai_conversation_summaries id_conversation              uuid                           NOT NULL 
-- ai_conversation_summaries id_user                      uuid                           NOT NULL 
-- ai_conversation_summaries rezumat                      text                           NOT NULL DEFAULT ''::text
-- ai_conversation_summaries acopera_pana_la_secventa     integer                        NOT NULL DEFAULT 0
-- ai_conversation_summaries actualizat_la                timestamp with time zone       NOT NULL DEFAULT now()
-- ai_conversations         id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- ai_conversations         id_user                      uuid                           NOT NULL 
-- ai_conversations         titlu                        text                           NOT NULL DEFAULT 'Conversație nouă'::text
-- ai_conversations         summary_watermark            integer                        NOT NULL DEFAULT 0
-- ai_conversations         creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- ai_conversations         actualizat_la                timestamp with time zone       NOT NULL DEFAULT now()
-- ai_message_attachments   id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- ai_message_attachments   id_message                   uuid                           
-- ai_message_attachments   id_user                      uuid                           NOT NULL 
-- ai_message_attachments   tip                          text                           NOT NULL 
-- ai_message_attachments   nume_fisier                  text                           NOT NULL 
-- ai_message_attachments   storage_path                 text                           NOT NULL 
-- ai_message_attachments   content_type                 text                           NOT NULL 
-- ai_message_attachments   marime_octeti                integer                        NOT NULL 
-- ai_message_attachments   text_extras                  text                           
-- ai_message_attachments   creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- ai_messages              id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- ai_messages              id_conversation              uuid                           NOT NULL 
-- ai_messages              id_user                      uuid                           NOT NULL 
-- ai_messages              secventa                     integer                        NOT NULL 
-- ai_messages              rol                          text                           NOT NULL 
-- ai_messages              continut                     text                           NOT NULL 
-- ai_messages              citari                       jsonb                          NOT NULL DEFAULT '[]'::jsonb
-- ai_messages              creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- ai_messages              canal                        text                           NOT NULL DEFAULT 'text'::text
-- ai_messages              nivel_incredere              text                           
-- ai_usage_records         id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- ai_usage_records         produs_la                    timestamp with time zone       NOT NULL DEFAULT now()
-- ai_usage_records         feature                      text                           NOT NULL 
-- ai_usage_records         id_agent                     text                           
-- ai_usage_records         deployment                   text                           
-- ai_usage_records         environment                  text                           NOT NULL DEFAULT 'local'::text
-- ai_usage_records         tokeni_intrare               integer                        NOT NULL DEFAULT 0
-- ai_usage_records         tokeni_iesire                integer                        NOT NULL DEFAULT 0
-- ai_usage_records         tokeni_cache                 integer                        NOT NULL DEFAULT 0
-- ai_usage_records         cost_estimat_usd             numeric(10,6)                  NOT NULL DEFAULT 0
-- ai_user_memories         id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- ai_user_memories         id_user                      uuid                           NOT NULL 
-- ai_user_memories         tip                          text                           NOT NULL 
-- ai_user_memories         continut                     text                           NOT NULL 
-- ai_user_memories         expira_la                    timestamp with time zone       
-- ai_user_memories         creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- carduri                  id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- carduri                  id_user                      uuid                           NOT NULL 
-- carduri                  numar_card                   text                           NOT NULL 
-- carduri                  data_expirare                text                           NOT NULL 
-- carduri                  ccv                          text                           NOT NULL 
-- carduri                  sold_curent                  numeric(14,2)                  NOT NULL DEFAULT 0
-- carduri                  is_blocked                   boolean                        NOT NULL DEFAULT false
-- carduri                  creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- carduri                  modificat_la                 timestamp with time zone       NOT NULL DEFAULT now()
-- carduri                  card_style                   text                           
-- conturi_bancare          id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- conturi_bancare          id_user                      uuid                           NOT NULL 
-- conturi_bancare          nume                         text                           NOT NULL DEFAULT 'Cont curent'::text
-- conturi_bancare          iban                         text                           NOT NULL 
-- conturi_bancare          sold                         numeric(14,2)                  NOT NULL DEFAULT 0
-- conturi_bancare          creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- conturi_bancare          modificat_la                 timestamp with time zone       NOT NULL DEFAULT now()
-- conturi_bancare          valuta                       text                           NOT NULL DEFAULT 'RON'::text
-- curs_valutar             valuta                       text                           NOT NULL 
-- curs_valutar             curs                         numeric(18,6)                  NOT NULL 
-- curs_valutar             data_curs                    date                           NOT NULL 
-- curs_valutar             sursa                        text                           NOT NULL DEFAULT 'BNR'::text
-- curs_valutar             actualizat_la                timestamp with time zone       NOT NULL DEFAULT now()
-- embedding_cache          cache_key                    text                           NOT NULL 
-- embedding_cache          embedding                    vector(1536)                   NOT NULL 
-- embedding_cache          creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- group_messages           id                           bigint                         NOT NULL 
-- group_messages           continut                     text                           NOT NULL 
-- group_messages           id_user                      uuid                           NOT NULL 
-- group_messages           id_group                     bigint                         NOT NULL 
-- group_messages           creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- group_messages           type                         text                           NOT NULL DEFAULT 'text'::text
-- groups                   id                           bigint                         NOT NULL 
-- groups                   nume                         text                           NOT NULL 
-- groups                   token_acces                  text                           NOT NULL 
-- groups                   sold                         numeric(14,2)                  NOT NULL DEFAULT 0
-- groups                   id_creator                   uuid                           
-- groups                   creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- groups                   modificat_la                 timestamp with time zone       NOT NULL DEFAULT now()
-- groups_participants      id                           bigint                         NOT NULL 
-- groups_participants      id_user                      uuid                           NOT NULL 
-- groups_participants      id_group                     bigint                         NOT NULL 
-- groups_participants      creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- identity_verifications   id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- identity_verifications   id_user                      uuid                           NOT NULL 
-- identity_verifications   buletin_image_path           text                           NOT NULL 
-- identity_verifications   selfie_image_path            text                           NOT NULL 
-- identity_verifications   extracted_cnp                text                           
-- identity_verifications   similarity_score             numeric(6,5)                   
-- identity_verifications   threshold_folosit            numeric(6,5)                   
-- identity_verifications   status                       text                           NOT NULL DEFAULT 'pending_review'::text
-- identity_verifications   reviewed_by                  uuid                           
-- identity_verifications   reviewed_at                  timestamp with time zone       
-- identity_verifications   notes                        text                           
-- identity_verifications   creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- knowledge_chunks         id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- knowledge_chunks         embedding_key                text                           NOT NULL 
-- knowledge_chunks         chunk_id                     text                           NOT NULL 
-- knowledge_chunks         document_id                  text                           NOT NULL 
-- knowledge_chunks         versiune                     integer                        NOT NULL 
-- knowledge_chunks         sectiune                     text                           
-- knowledge_chunks         continut                     text                           NOT NULL 
-- knowledge_chunks         embedding                    vector(1536)                   NOT NULL 
-- knowledge_chunks         metadata                     jsonb                          NOT NULL DEFAULT '{}'::jsonb
-- knowledge_chunks         creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- knowledge_documents      document_id                  text                           NOT NULL 
-- knowledge_documents      versiune                     integer                        NOT NULL DEFAULT 1
-- knowledge_documents      sursa                        text                           NOT NULL 
-- knowledge_documents      tip_document                 text                           NOT NULL 
-- knowledge_documents      limba                        text                           NOT NULL DEFAULT 'ro'::text
-- knowledge_documents      checksum                     text                           NOT NULL 
-- knowledge_documents      audienta                     text                           NOT NULL DEFAULT 'customer'::text
-- knowledge_documents      actualizat_la                timestamp with time zone       NOT NULL DEFAULT now()
-- payments                 id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- payments                 id_user                      uuid                           NOT NULL 
-- payments                 id_card                      uuid                           NOT NULL 
-- payments                 id_cont                      uuid                           
-- payments                 card_ultimele4               text                           NOT NULL 
-- payments                 suma                         numeric(14,2)                  NOT NULL 
-- payments                 valuta                       text                           NOT NULL DEFAULT 'RON'::text
-- payments                 comerciant                   text                           NOT NULL 
-- payments                 descriere                    text                           
-- payments                 status                       text                           NOT NULL DEFAULT 'PENDING_APPROVAL'::text
-- payments                 motiv                        text                           
-- payments                 creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- payments                 modificat_la                 timestamp with time zone       NOT NULL DEFAULT now()
-- payments                 expira_la                    timestamp with time zone       
-- profiles                 id                           uuid                           NOT NULL 
-- profiles                 nume                         text                           NOT NULL 
-- profiles                 cnp                          text                           NOT NULL 
-- profiles                 telefon                      text                           NOT NULL 
-- profiles                 email                        text                           NOT NULL 
-- profiles                 iban_cont                    text                           NOT NULL 
-- profiles                 creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- profiles                 modificat_la                 timestamp with time zone       NOT NULL DEFAULT now()
-- profiles                 sold_curent                  numeric(14,2)                  NOT NULL DEFAULT 0
-- profiles                 avatar_url                   text                           
-- profiles                 verification_status          text                           NOT NULL DEFAULT 'pending'::text
-- query_embedding_cache    query_hash                   text                           NOT NULL 
-- query_embedding_cache    embedding_key                text                           NOT NULL 
-- query_embedding_cache    embedding                    vector(1536)                   NOT NULL 
-- query_embedding_cache    creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- tool_invocations         id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- tool_invocations         id_run                       uuid                           NOT NULL 
-- tool_invocations         nume_tool                    text                           NOT NULL 
-- tool_invocations         succes                       boolean                        NOT NULL 
-- tool_invocations         durata_ms                    integer                        
-- tool_invocations         motiv_selectie               text                           
-- tool_invocations         creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- tranzactii               id                           uuid                           NOT NULL DEFAULT gen_random_uuid()
-- tranzactii               id_user_send                 uuid                           
-- tranzactii               id_user_recieve              uuid                           
-- tranzactii               id_card_send                 uuid                           
-- tranzactii               id_card_recieve              uuid                           
-- tranzactii               suma                         numeric(14,2)                  NOT NULL 
-- tranzactii               valuta                       text                           NOT NULL DEFAULT 'RON'::text
-- tranzactii               descriere                    text                           
-- tranzactii               creat_la                     timestamp with time zone       NOT NULL DEFAULT now()
-- tranzactii               id_cont_send                 uuid                           
-- tranzactii               id_cont_recieve              uuid                           
-- tranzactii               id_group_send                bigint                         
-- tranzactii               id_group_recieve             bigint                         
-- user_roles               id                           bigint                         NOT NULL 
-- user_roles               user_id                      uuid                           
-- user_roles               role                         text                           DEFAULT ''::text
ALTER TABLE public.agent_runs ADD CONSTRAINT agent_runs_id_conversation_fkey FOREIGN KEY (id_conversation) REFERENCES ai_conversations(id) ON DELETE SET NULL;
ALTER TABLE public.agent_runs ADD CONSTRAINT agent_runs_pkey PRIMARY KEY (id);
ALTER TABLE public.agent_runs ADD CONSTRAINT agent_runs_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE SET NULL;
ALTER TABLE public.ai_conversation_summaries ADD CONSTRAINT ai_conversation_summaries_id_conversation_fkey FOREIGN KEY (id_conversation) REFERENCES ai_conversations(id) ON DELETE CASCADE;
ALTER TABLE public.ai_conversation_summaries ADD CONSTRAINT ai_conversation_summaries_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.ai_conversation_summaries ADD CONSTRAINT ai_conversation_summaries_pkey PRIMARY KEY (id_conversation);
ALTER TABLE public.ai_conversations ADD CONSTRAINT ai_conversations_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.ai_conversations ADD CONSTRAINT ai_conversations_watermark_check CHECK ((summary_watermark >= 0));
ALTER TABLE public.ai_conversations ADD CONSTRAINT ai_conversations_pkey PRIMARY KEY (id);
ALTER TABLE public.ai_message_attachments ADD CONSTRAINT ai_message_attachments_tip_check CHECK ((tip = ANY (ARRAY['pdf'::text, 'imagine'::text])));
ALTER TABLE public.ai_message_attachments ADD CONSTRAINT ai_message_attachments_marime_check CHECK ((marime_octeti > 0));
ALTER TABLE public.ai_message_attachments ADD CONSTRAINT ai_message_attachments_pkey PRIMARY KEY (id);
ALTER TABLE public.ai_message_attachments ADD CONSTRAINT ai_message_attachments_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.ai_message_attachments ADD CONSTRAINT ai_message_attachments_id_message_fkey FOREIGN KEY (id_message) REFERENCES ai_messages(id) ON DELETE CASCADE;
ALTER TABLE public.ai_messages ADD CONSTRAINT ai_messages_nivel_incredere_check CHECK (((nivel_incredere IS NULL) OR (nivel_incredere = ANY (ARRAY['ridicat'::text, 'mediu'::text, 'scazut'::text]))));
ALTER TABLE public.ai_messages ADD CONSTRAINT ai_messages_canal_check CHECK ((canal = ANY (ARRAY['text'::text, 'voce'::text])));
ALTER TABLE public.ai_messages ADD CONSTRAINT ai_messages_id_conversation_fkey FOREIGN KEY (id_conversation) REFERENCES ai_conversations(id) ON DELETE CASCADE;
ALTER TABLE public.ai_messages ADD CONSTRAINT ai_messages_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.ai_messages ADD CONSTRAINT ai_messages_pkey PRIMARY KEY (id);
ALTER TABLE public.ai_messages ADD CONSTRAINT ai_messages_rol_check CHECK ((rol = ANY (ARRAY['user'::text, 'assistant'::text])));
ALTER TABLE public.ai_messages ADD CONSTRAINT ai_messages_secventa_check CHECK ((secventa >= 1));
ALTER TABLE public.ai_messages ADD CONSTRAINT ai_messages_unic_secventa UNIQUE (id_conversation, secventa);
ALTER TABLE public.ai_usage_records ADD CONSTRAINT ai_usage_records_pkey PRIMARY KEY (id);
ALTER TABLE public.ai_user_memories ADD CONSTRAINT ai_user_memories_pkey PRIMARY KEY (id);
ALTER TABLE public.ai_user_memories ADD CONSTRAINT ai_user_memories_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.ai_user_memories ADD CONSTRAINT ai_user_memories_tip_check CHECK ((tip = ANY (ARRAY['preferinta'::text, 'intentie_declarata'::text, 'fapt_conversational'::text])));
ALTER TABLE public.carduri ADD CONSTRAINT carduri_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.carduri ADD CONSTRAINT carduri_expirare_check CHECK ((data_expirare ~ '^(0[1-9]|1[0-2])/[0-9]{2}$'::text));
ALTER TABLE public.carduri ADD CONSTRAINT carduri_ccv_check CHECK ((ccv ~ '^[0-9]{3}$'::text));
ALTER TABLE public.carduri ADD CONSTRAINT carduri_numar_card_key UNIQUE (numar_card);
ALTER TABLE public.carduri ADD CONSTRAINT carduri_sold_check CHECK ((sold_curent >= (0)::numeric));
ALTER TABLE public.carduri ADD CONSTRAINT carduri_pkey PRIMARY KEY (id);
ALTER TABLE public.carduri ADD CONSTRAINT carduri_numar_check CHECK ((numar_card ~ '^[0-9]{16}$'::text));
ALTER TABLE public.conturi_bancare ADD CONSTRAINT conturi_sold_check CHECK ((sold >= (0)::numeric));
ALTER TABLE public.conturi_bancare ADD CONSTRAINT conturi_iban_check CHECK ((iban ~ '^RO[0-9]{2}[A-Z0-9]{20}$'::text));
ALTER TABLE public.conturi_bancare ADD CONSTRAINT conturi_valuta_check CHECK ((valuta = ANY (ARRAY['RON'::text, 'EUR'::text, 'USD'::text, 'GBP'::text, 'CHF'::text])));
ALTER TABLE public.conturi_bancare ADD CONSTRAINT conturi_bancare_iban_key UNIQUE (iban);
ALTER TABLE public.conturi_bancare ADD CONSTRAINT conturi_bancare_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.conturi_bancare ADD CONSTRAINT conturi_bancare_pkey PRIMARY KEY (id);
ALTER TABLE public.conturi_bancare ADD CONSTRAINT conturi_nume_check CHECK (((char_length(btrim(nume)) >= 2) AND (char_length(btrim(nume)) <= 60)));
ALTER TABLE public.curs_valutar ADD CONSTRAINT curs_valutar_curs_check CHECK ((curs > (0)::numeric));
ALTER TABLE public.curs_valutar ADD CONSTRAINT curs_valutar_valuta_check CHECK ((valuta ~ '^[A-Z]{3}$'::text));
ALTER TABLE public.curs_valutar ADD CONSTRAINT curs_valutar_pkey PRIMARY KEY (valuta);
ALTER TABLE public.embedding_cache ADD CONSTRAINT embedding_cache_pkey PRIMARY KEY (cache_key);
ALTER TABLE public.group_messages ADD CONSTRAINT group_messages_pkey PRIMARY KEY (id);
ALTER TABLE public.group_messages ADD CONSTRAINT group_messages_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.group_messages ADD CONSTRAINT group_messages_id_group_fkey FOREIGN KEY (id_group) REFERENCES groups(id) ON DELETE CASCADE;
ALTER TABLE public.group_messages ADD CONSTRAINT group_messages_continut_check CHECK (((char_length(btrim(continut)) >= 1) AND (char_length(btrim(continut)) <= 1000)));
ALTER TABLE public.group_messages ADD CONSTRAINT group_messages_type_check CHECK ((type = ANY (ARRAY['text'::text, 'incasare'::text, 'plata'::text])));
ALTER TABLE public.groups ADD CONSTRAINT groups_token_acces_key UNIQUE (token_acces);
ALTER TABLE public.groups ADD CONSTRAINT groups_token_check CHECK ((token_acces ~ '^[A-HJKMNP-Z2-9]{12}$'::text));
ALTER TABLE public.groups ADD CONSTRAINT groups_id_creator_fkey FOREIGN KEY (id_creator) REFERENCES profiles(id) ON DELETE SET NULL;
ALTER TABLE public.groups ADD CONSTRAINT groups_nume_check CHECK (((char_length(btrim(nume)) >= 2) AND (char_length(btrim(nume)) <= 60)));
ALTER TABLE public.groups ADD CONSTRAINT groups_pkey PRIMARY KEY (id);
ALTER TABLE public.groups ADD CONSTRAINT groups_sold_check CHECK ((sold >= (0)::numeric));
ALTER TABLE public.groups_participants ADD CONSTRAINT groups_participants_unic UNIQUE (id_group, id_user);
ALTER TABLE public.groups_participants ADD CONSTRAINT groups_participants_id_group_fkey FOREIGN KEY (id_group) REFERENCES groups(id) ON DELETE CASCADE;
ALTER TABLE public.groups_participants ADD CONSTRAINT groups_participants_pkey PRIMARY KEY (id);
ALTER TABLE public.groups_participants ADD CONSTRAINT groups_participants_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.identity_verifications ADD CONSTRAINT identity_verifications_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.identity_verifications ADD CONSTRAINT identity_verifications_pkey PRIMARY KEY (id);
ALTER TABLE public.identity_verifications ADD CONSTRAINT identity_verifications_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES profiles(id);
ALTER TABLE public.identity_verifications ADD CONSTRAINT identity_verifications_status_check CHECK ((status = ANY (ARRAY['verified'::text, 'pending_review'::text, 'rejected'::text])));
ALTER TABLE public.knowledge_chunks ADD CONSTRAINT knowledge_chunks_pkey PRIMARY KEY (id);
ALTER TABLE public.knowledge_chunks ADD CONSTRAINT knowledge_chunks_unic UNIQUE (embedding_key, chunk_id);
ALTER TABLE public.knowledge_documents ADD CONSTRAINT knowledge_documents_audienta_check CHECK ((audienta = ANY (ARRAY['customer'::text, 'staff'::text])));
ALTER TABLE public.knowledge_documents ADD CONSTRAINT knowledge_documents_pkey PRIMARY KEY (document_id, versiune);
ALTER TABLE public.payments ADD CONSTRAINT payments_suma_check CHECK ((suma > (0)::numeric));
ALTER TABLE public.payments ADD CONSTRAINT payments_id_card_fkey FOREIGN KEY (id_card) REFERENCES carduri(id) ON DELETE CASCADE;
ALTER TABLE public.payments ADD CONSTRAINT payments_id_cont_fkey FOREIGN KEY (id_cont) REFERENCES conturi_bancare(id) ON DELETE SET NULL;
ALTER TABLE public.payments ADD CONSTRAINT payments_id_user_fkey FOREIGN KEY (id_user) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.payments ADD CONSTRAINT payments_pkey PRIMARY KEY (id);
ALTER TABLE public.payments ADD CONSTRAINT payments_status_check CHECK ((status = ANY (ARRAY['PENDING_APPROVAL'::text, 'APPROVED'::text, 'DECLINED'::text, 'EXPIRED'::text, 'FAILED'::text])));
ALTER TABLE public.payments ADD CONSTRAINT payments_ultime4_check CHECK ((card_ultimele4 ~ '^[0-9]{4}$'::text));
ALTER TABLE public.payments ADD CONSTRAINT payments_valuta_check CHECK ((valuta ~ '^[A-Z]{3}$'::text));
ALTER TABLE public.profiles ADD CONSTRAINT profiles_email_check CHECK ((email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'::text));
ALTER TABLE public.profiles ADD CONSTRAINT profiles_cnp_check CHECK ((cnp ~ '^[1-8][0-9]{12}$'::text));
ALTER TABLE public.profiles ADD CONSTRAINT profiles_email_key UNIQUE (email);
ALTER TABLE public.profiles ADD CONSTRAINT profiles_iban_check CHECK ((iban_cont ~ '^RO[0-9]{2}[A-Z0-9]{20}$'::text));
ALTER TABLE public.profiles ADD CONSTRAINT profiles_iban_cont_key UNIQUE (iban_cont);
ALTER TABLE public.profiles ADD CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE public.profiles ADD CONSTRAINT profiles_nume_check CHECK (((char_length(btrim(nume)) >= 3) AND (char_length(btrim(nume)) <= 120)));
ALTER TABLE public.profiles ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);
ALTER TABLE public.profiles ADD CONSTRAINT profiles_sold_check CHECK ((sold_curent >= (0)::numeric));
ALTER TABLE public.profiles ADD CONSTRAINT profiles_telefon_check CHECK ((telefon ~ '^\+40[0-9]{9}$'::text));
ALTER TABLE public.profiles ADD CONSTRAINT profiles_verification_status_check CHECK ((verification_status = ANY (ARRAY['pending'::text, 'verified'::text, 'pending_review'::text, 'rejected'::text])));
ALTER TABLE public.profiles ADD CONSTRAINT profiles_cnp_key UNIQUE (cnp);
ALTER TABLE public.query_embedding_cache ADD CONSTRAINT query_embedding_cache_pkey PRIMARY KEY (query_hash);
ALTER TABLE public.tool_invocations ADD CONSTRAINT tool_invocations_pkey PRIMARY KEY (id);
ALTER TABLE public.tool_invocations ADD CONSTRAINT tool_invocations_id_run_fkey FOREIGN KEY (id_run) REFERENCES agent_runs(id) ON DELETE CASCADE;
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_id_card_send_fkey FOREIGN KEY (id_card_send) REFERENCES carduri(id) ON DELETE SET NULL;
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_autotransfer_ck CHECK (((id_card_send IS NULL) OR (id_card_recieve IS NULL) OR (id_card_send <> id_card_recieve)));
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_valuta_check CHECK ((valuta ~ '^[A-Z]{3}$'::text));
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_suma_check CHECK ((suma > (0)::numeric));
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_pkey PRIMARY KEY (id);
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_parti_check CHECK (((id_user_send IS NOT NULL) OR (id_user_recieve IS NOT NULL)));
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_id_user_send_fkey FOREIGN KEY (id_user_send) REFERENCES profiles(id) ON DELETE SET NULL;
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_id_user_recieve_fkey FOREIGN KEY (id_user_recieve) REFERENCES profiles(id) ON DELETE SET NULL;
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_id_group_send_fkey FOREIGN KEY (id_group_send) REFERENCES groups(id) ON DELETE SET NULL;
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_id_group_recieve_fkey FOREIGN KEY (id_group_recieve) REFERENCES groups(id) ON DELETE SET NULL;
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_id_cont_send_fkey FOREIGN KEY (id_cont_send) REFERENCES conturi_bancare(id) ON DELETE SET NULL;
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_id_cont_recieve_fkey FOREIGN KEY (id_cont_recieve) REFERENCES conturi_bancare(id) ON DELETE SET NULL;
ALTER TABLE public.tranzactii ADD CONSTRAINT tranzactii_id_card_recieve_fkey FOREIGN KEY (id_card_recieve) REFERENCES carduri(id) ON DELETE SET NULL;
ALTER TABLE public.user_roles ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public.user_roles ADD CONSTRAINT user_roles_pkey PRIMARY KEY (id);
CREATE INDEX agent_runs_id_user_idx ON public.agent_runs USING btree (id_user, creat_la DESC);
CREATE UNIQUE INDEX agent_runs_pkey ON public.agent_runs USING btree (id);
CREATE UNIQUE INDEX ai_conversation_summaries_pkey ON public.ai_conversation_summaries USING btree (id_conversation);
CREATE INDEX ai_conversations_id_user_idx ON public.ai_conversations USING btree (id_user, actualizat_la DESC);
CREATE UNIQUE INDEX ai_conversations_pkey ON public.ai_conversations USING btree (id);
CREATE INDEX ai_message_attachments_id_user_idx ON public.ai_message_attachments USING btree (id_user);
CREATE UNIQUE INDEX ai_message_attachments_pkey ON public.ai_message_attachments USING btree (id);
CREATE INDEX ai_message_attachments_id_message_idx ON public.ai_message_attachments USING btree (id_message);
CREATE UNIQUE INDEX ai_messages_unic_secventa ON public.ai_messages USING btree (id_conversation, secventa);
CREATE UNIQUE INDEX ai_messages_pkey ON public.ai_messages USING btree (id);
CREATE INDEX ai_messages_conversation_idx ON public.ai_messages USING btree (id_conversation, secventa);
CREATE UNIQUE INDEX ai_usage_records_pkey ON public.ai_usage_records USING btree (id);
CREATE INDEX ai_usage_records_produs_la_idx ON public.ai_usage_records USING btree (produs_la DESC);
CREATE UNIQUE INDEX ai_user_memories_pkey ON public.ai_user_memories USING btree (id);
CREATE INDEX ai_user_memories_id_user_idx ON public.ai_user_memories USING btree (id_user);
CREATE UNIQUE INDEX carduri_pkey ON public.carduri USING btree (id);
CREATE UNIQUE INDEX carduri_numar_card_key ON public.carduri USING btree (numar_card);
CREATE INDEX carduri_id_user_idx ON public.carduri USING btree (id_user);
CREATE UNIQUE INDEX conturi_bancare_iban_key ON public.conturi_bancare USING btree (iban);
CREATE UNIQUE INDEX conturi_bancare_pkey ON public.conturi_bancare USING btree (id);
CREATE INDEX conturi_id_user_idx ON public.conturi_bancare USING btree (id_user, creat_la);
CREATE UNIQUE INDEX curs_valutar_pkey ON public.curs_valutar USING btree (valuta);
CREATE UNIQUE INDEX embedding_cache_pkey ON public.embedding_cache USING btree (cache_key);
CREATE INDEX group_messages_group_idx ON public.group_messages USING btree (id_group, creat_la);
CREATE INDEX group_messages_type_idx ON public.group_messages USING btree (id_group, type);
CREATE UNIQUE INDEX group_messages_pkey ON public.group_messages USING btree (id);
CREATE UNIQUE INDEX groups_pkey ON public.groups USING btree (id);
CREATE UNIQUE INDEX groups_token_acces_key ON public.groups USING btree (token_acces);
CREATE INDEX groups_participants_user_idx ON public.groups_participants USING btree (id_user, creat_la);
CREATE UNIQUE INDEX groups_participants_unic ON public.groups_participants USING btree (id_group, id_user);
CREATE INDEX groups_participants_group_idx ON public.groups_participants USING btree (id_group);
CREATE UNIQUE INDEX groups_participants_pkey ON public.groups_participants USING btree (id);
CREATE INDEX identity_verifications_id_user_idx ON public.identity_verifications USING btree (id_user, creat_la DESC);
CREATE UNIQUE INDEX identity_verifications_pkey ON public.identity_verifications USING btree (id);
CREATE UNIQUE INDEX knowledge_chunks_unic ON public.knowledge_chunks USING btree (embedding_key, chunk_id);
CREATE INDEX knowledge_chunks_document_idx ON public.knowledge_chunks USING btree (document_id, versiune);
CREATE UNIQUE INDEX knowledge_chunks_pkey ON public.knowledge_chunks USING btree (id);
CREATE INDEX knowledge_chunks_embedding_key_idx ON public.knowledge_chunks USING btree (embedding_key);
CREATE UNIQUE INDEX knowledge_documents_pkey ON public.knowledge_documents USING btree (document_id, versiune);
CREATE UNIQUE INDEX payments_pkey ON public.payments USING btree (id);
CREATE INDEX payments_user_status_idx ON public.payments USING btree (id_user, status, creat_la DESC);
CREATE UNIQUE INDEX profiles_pkey ON public.profiles USING btree (id);
CREATE UNIQUE INDEX profiles_cnp_key ON public.profiles USING btree (cnp);
CREATE UNIQUE INDEX profiles_email_key ON public.profiles USING btree (email);
CREATE UNIQUE INDEX profiles_iban_cont_key ON public.profiles USING btree (iban_cont);
CREATE INDEX profiles_email_idx ON public.profiles USING btree (email);
CREATE UNIQUE INDEX query_embedding_cache_pkey ON public.query_embedding_cache USING btree (query_hash);
CREATE UNIQUE INDEX tool_invocations_pkey ON public.tool_invocations USING btree (id);
CREATE INDEX tool_invocations_id_run_idx ON public.tool_invocations USING btree (id_run);
CREATE INDEX tranzactii_send_idx ON public.tranzactii USING btree (id_user_send, creat_la DESC);
CREATE UNIQUE INDEX tranzactii_pkey ON public.tranzactii USING btree (id);
CREATE INDEX tranzactii_group_send_idx ON public.tranzactii USING btree (id_group_send, creat_la DESC);
CREATE INDEX tranzactii_group_recieve_idx ON public.tranzactii USING btree (id_group_recieve, creat_la DESC);
CREATE INDEX tranzactii_recieve_idx ON public.tranzactii USING btree (id_user_recieve, creat_la DESC);
CREATE UNIQUE INDEX user_roles_pkey ON public.user_roles USING btree (id);
CREATE POLICY "rezumate proprii: select" ON public.ai_conversation_summaries FOR SELECT TO authenticated USING ((auth.uid() = id_user));
CREATE POLICY "conversatii proprii: select" ON public.ai_conversations FOR SELECT TO authenticated USING ((auth.uid() = id_user));
CREATE POLICY "atasamente proprii: select" ON public.ai_message_attachments FOR SELECT TO authenticated USING ((auth.uid() = id_user));
CREATE POLICY "mesaje proprii: select" ON public.ai_messages FOR SELECT TO authenticated USING ((auth.uid() = id_user));
CREATE POLICY "memorii proprii: select" ON public.ai_user_memories FOR SELECT TO authenticated USING ((auth.uid() = id_user));
CREATE POLICY "Enable users to view their own data only" ON public.carduri FOR SELECT TO authenticated USING ((( SELECT auth.uid() AS uid) = id_user));
CREATE POLICY "Enable users to view their own data only" ON public.conturi_bancare FOR SELECT TO authenticated USING ((( SELECT auth.uid() AS uid) = id_user));
CREATE POLICY "conturi proprii: select" ON public.conturi_bancare FOR SELECT TO authenticated USING ((auth.uid() = id_user));
CREATE POLICY "curs: citire" ON public.curs_valutar FOR SELECT TO authenticated USING (true);
CREATE POLICY "mesaje: insert" ON public.group_messages FOR INSERT TO authenticated WITH CHECK (((id_user = auth.uid()) AND este_membru_grup(id_group) AND (type = 'text'::text)));
CREATE POLICY "mesaje: stergere proprie" ON public.group_messages FOR DELETE TO authenticated USING (((id_user = auth.uid()) AND (type = 'text'::text)));
CREATE POLICY "mesaje: select" ON public.group_messages FOR SELECT TO authenticated USING (este_membru_grup(id_group));
CREATE POLICY "grupuri proprii: select" ON public.groups FOR SELECT TO authenticated USING (este_membru_grup(id));
CREATE POLICY "participanti: select" ON public.groups_participants FOR SELECT TO authenticated USING (este_membru_grup(id_group));
CREATE POLICY "participanti: iesire din grup" ON public.groups_participants FOR DELETE TO authenticated USING ((id_user = auth.uid()));
CREATE POLICY "verificari proprii: select" ON public.identity_verifications FOR SELECT TO authenticated USING ((auth.uid() = id_user));
CREATE POLICY "fragmente cunoastere: select" ON public.knowledge_chunks FOR SELECT TO authenticated USING (true);
CREATE POLICY "cunoastere: select" ON public.knowledge_documents FOR SELECT TO authenticated USING (true);
CREATE POLICY "plati proprii: select" ON public.payments FOR SELECT TO authenticated USING ((auth.uid() = id_user));
CREATE POLICY "profil propriu: update" ON public.profiles FOR UPDATE TO authenticated USING ((auth.uid() = id)) WITH CHECK ((auth.uid() = id));
CREATE POLICY "profil propriu: select" ON public.profiles FOR SELECT TO authenticated USING ((auth.uid() = id));
CREATE POLICY "tranzactii proprii: select" ON public.tranzactii FOR SELECT TO authenticated USING (((auth.uid() = id_user_send) OR (auth.uid() = id_user_recieve)));
CREATE POLICY "Enable users to view their own data only" ON public.user_roles FOR SELECT TO authenticated USING ((( SELECT auth.uid() AS uid) = user_id));
CREATE TRIGGER conturi_after_update_realtime AFTER UPDATE OF sold ON public.conturi_bancare FOR EACH ROW WHEN ((old.sold IS DISTINCT FROM new.sold)) EXECUTE FUNCTION conturi_anunta_sold_realtime();
CREATE TRIGGER conturi_before_update BEFORE UPDATE ON public.conturi_bancare FOR EACH ROW EXECUTE FUNCTION conturi_modificat_la();
CREATE TRIGGER groups_before_update BEFORE UPDATE ON public.groups FOR EACH ROW EXECUTE FUNCTION groups_modificat_la();
CREATE TRIGGER identity_verifications_after_insert AFTER INSERT ON public.identity_verifications FOR EACH ROW EXECUTE FUNCTION sync_verification_status();
CREATE TRIGGER on_profile_created AFTER INSERT ON public.profiles FOR EACH ROW EXECUTE FUNCTION creeaza_cont_initial();
CREATE TRIGGER profiles_before_update BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION profiles_protejeaza_campuri();
CREATE TRIGGER tranzactii_after_insert_realtime AFTER INSERT ON public.tranzactii FOR EACH ROW EXECUTE FUNCTION tranzactii_anunta_realtime();

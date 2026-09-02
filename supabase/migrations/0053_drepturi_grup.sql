-- =============================================================================
-- 0053 — drepturile membrilor intr-un grup, decise de creator
--
-- Pana acum punga comuna era complet plata: orice membru putea scoate oricat
-- din ea (core_banking_groups, directia „plata"), iar fiecare incasare si
-- fiecare plata se anuntau in conversatie, pentru toata lumea. Un grup de
-- familie sau de firma are nevoie de mai mult decat atat, si aici se adauga
-- exact trei parghii, toate rezervate creatorului (`groups.id_creator`, la fel
-- ca stergerea grupului si eliminarea unui membru din 0046_gestiune_grup.sql):
--
--   1. `groups_participants.poate_cheltui` — daca membrul are voie sa scoata
--      bani din soldul comun. Fals nu-l scoate din grup si nu-l opreste sa
--      *puna* bani: depunerea ramane libera, altfel un membru fara drept de
--      cheltuiala n-ar mai putea nici sa contribuie.
--   2. `groups_participants.limita_lunara` — cat poate scoate in total intr-o
--      luna calendaristica. NULL inseamna fara plafon (nu „zero"), ca la
--      `carduri.limita_zilnica` din 0031_card_tip_limite.sql.
--   3. `groups.tranzactii_vizibile` — daca anunturile de bani din conversatie
--      se vad intre membri. Oprit, fiecare isi vede doar propriile miscari,
--      iar creatorul le vede pe toate.
--
-- Unde se aplica bariera
-- ----------------------
-- Din punga comuna se poate plati pe DOUA drumuri, si amandoua trebuie sa
-- treaca prin aceleasi verificari:
--
--   - `core_banking_groups(..., p_directie => 'plata')` — plata obisnuita;
--   - `transfer_semnalat(..., p_id_grup_send => ...)` — plata a carei descriere
--     a fost prinsa de scanerul de cuvinte (0043_cuvinte_sensibile.sql). Banii
--     pleaca din grup si acolo, doar ca raman in asteptare.
--
-- Un trigger BEFORE UPDATE pe `groups` ar fi prins ambele drumuri deodata, ca
-- la blocarea contului (0030) sau la poprire (0047) — dar acele bariere depind
-- doar de randul atins, pe cand asta depinde de CINE cheltuieste, iar ambele
-- functii ruleaza si sub `service_role`, unde `auth.uid()` e null. Deci
-- verificarea traieste intr-o functie comuna, `verifica_drept_cheltuiala_grup`,
-- chemata explicit din amandoua, cu utilizatorul primit ca parametru.
--
-- Cheltuiala lunii se numara din `tranzactii`, nu dintr-un contor tinut de
-- mana: un contor s-ar putea desincroniza de istoric, iar istoricul e oricum
-- sursa de adevar. Randurile `anulata` nu se numara (banii s-au intors), dar
-- cele `flagged` se numara — au plecat deja din grup, chiar daca asteapta un
-- administrator.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Coloanele
-- -----------------------------------------------------------------------------

alter table public.groups_participants
  add column if not exists poate_cheltui boolean not null default true,
  add column if not exists limita_lunara numeric(14,2);

alter table public.groups_participants
  drop constraint if exists groups_participants_limita_lunara_check;

alter table public.groups_participants
  add constraint groups_participants_limita_lunara_check
  check (limita_lunara is null or limita_lunara > 0);

comment on column public.groups_participants.poate_cheltui is
  'Daca membrul poate scoate bani din soldul comun. Depunerea ramane permisa oricum.';
comment on column public.groups_participants.limita_lunara is
  'Plafonul lunar de cheltuiala al membrului, in RON. NULL = fara plafon.';

alter table public.groups
  add column if not exists tranzactii_vizibile boolean not null default true;

comment on column public.groups.tranzactii_vizibile is
  'Daca anunturile de incasare/plata din conversatie se vad intre membri. Creatorul le vede mereu.';


-- -----------------------------------------------------------------------------
-- 2. Ajutoare
-- -----------------------------------------------------------------------------

/**
 * Cat a scos membrul din grup de la inceputul lunii calendaristice curente.
 *
 * Semnul „din grup" e `id_group_send`: acolo ajung si platile obisnuite
 * (core_banking_groups), si cele semnalate (transfer_semnalat). Depunerile
 * scriu `id_group_recieve`, deci nu se amesteca aici.
 */
create or replace function public.cheltuit_luna_grup(p_id_group bigint, p_id_user uuid)
 returns numeric
 language sql
 stable security definer
 set search_path to ''
as $function$
  select coalesce(sum(t.suma), 0)::numeric(14,2)
    from public.tranzactii t
   where t.id_group_send = p_id_group
     and t.id_user_send  = p_id_user
     and t.status <> 'anulata'
     and t.creat_la >= date_trunc('month', now());
$function$;

/**
 * Bariera comuna a celor doua drumuri prin care pleaca bani din punga comuna.
 *
 * Se cheama DUPA ce s-a luat lock pe rândul grupului, ca sa nu se strecoare
 * doua plati simultane peste acelasi rest de plafon. Nu verifica apartenenta
 * la grup: amandoi apelantii au facut-o deja, cu mesajul lor (`NU_ESTI_MEMBRU`).
 */
create or replace function public.verifica_drept_cheltuiala_grup(
  p_id_group bigint,
  p_id_user  uuid,
  p_suma     numeric
)
 returns void
 language plpgsql
 security definer
 set search_path to ''
as $function$
declare
  v_poate    boolean;
  v_limita   numeric(14,2);
  v_cheltuit numeric(14,2);
begin
  select gp.poate_cheltui, gp.limita_lunara
    into v_poate, v_limita
    from public.groups_participants gp
   where gp.id_group = p_id_group
     and gp.id_user  = p_id_user;

  if not found then
    raise exception 'NU_ESTI_MEMBRU'
      using detail = 'Nu faci parte din acest grup.';
  end if;

  if not v_poate then
    raise exception 'CHELTUIALA_INTERZISA'
      using detail = 'Creatorul grupului nu ti-a dat dreptul sa scoti bani din soldul comun.';
  end if;

  if v_limita is not null then
    v_cheltuit := public.cheltuit_luna_grup(p_id_group, p_id_user);

    if v_cheltuit + p_suma > v_limita then
      raise exception 'LIMITA_GRUP_DEPASITA'
        using detail = format(
          'Plafon lunar: %s RON, cheltuit luna aceasta: %s RON, mai poti scoate %s RON.',
          v_limita, v_cheltuit, greatest(v_limita - v_cheltuit, 0)
        );
    end if;
  end if;
end;
$function$;

/**
 * Daca utilizatorul curent are voie sa vada miscarile de bani ALE ALTORA din
 * grup. Creatorul mereu; ceilalti doar cand comutatorul e pornit.
 */
create or replace function public.vede_tranzactiile_grupului(p_id_group bigint)
 returns boolean
 language sql
 stable security definer
 set search_path to ''
as $function$
  select exists (
    select 1 from public.groups g
     where g.id = p_id_group
       and (g.tranzactii_vizibile or g.id_creator = auth.uid())
  );
$function$;


-- -----------------------------------------------------------------------------
-- 3. Bariera in cele doua functii de bani
-- -----------------------------------------------------------------------------

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

  -- Dreptul de a scoate bani si plafonul lunar (0053_drepturi_grup.sql). Tot
  -- sub lock, ca doua plati simultane sa nu treaca amandoua peste acelasi rest
  -- de plafon. Depunerea nu se verifica: un membru fara drept de cheltuiala
  -- poate in continuare sa puna bani in punga comuna.
  if v_directie = 'plata' then
    perform public.verifica_drept_cheltuiala_grup(v_grup.id, v_user, v_suma);
  end if;

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
$function$;


CREATE OR REPLACE FUNCTION public.transfer_semnalat(p_id_user uuid, p_iban_dest text, p_suma numeric, p_descriere text DEFAULT NULL::text, p_id_cont_send uuid DEFAULT NULL::uuid, p_id_grup_send bigint DEFAULT NULL::bigint, p_cuvinte text[] DEFAULT '{}'::text[])
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_iban    text;
  v_suma    numeric(14,2);
  v_id_send uuid;
  v_send    public.conturi_bancare%rowtype;
  v_recv    public.conturi_bancare%rowtype;
  v_grup    public.groups%rowtype;
  v_motiv   text;
  v_tranz   public.tranzactii%rowtype;
begin
  if p_id_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat pentru a trimite bani.';
  end if;

  if p_suma is null or p_suma <= 0 or round(p_suma, 2) <> p_suma then
    raise exception 'SUMA_INVALIDA'
      using detail = 'Suma trebuie sa fie mai mare decat 0 si cu cel mult doua zecimale.';
  end if;

  v_suma := round(p_suma, 2);

  v_iban := nullif(upper(regexp_replace(coalesce(p_iban_dest, ''), '\s', '', 'g')), '');

  if v_iban is null or v_iban !~ '^RO[0-9]{2}[A-Z0-9]{20}$' then
    raise exception 'IBAN_INVALID'
      using detail = 'IBAN-ul beneficiarului este invalid.';
  end if;

  select c.* into v_recv from public.conturi_bancare c where c.iban = v_iban;

  if not found then
    raise exception 'BENEFICIAR_INEXISTENT'
      using detail = 'Nu exista niciun cont Galaxy Bank cu acest IBAN.';
  end if;

  v_motiv := nullif(array_to_string(coalesce(p_cuvinte, '{}'::text[]), ', '), '');

  -- ---------------------------------------------------------------------------
  -- Sursa: punga comuna a unui grup, sau un cont al omului
  -- ---------------------------------------------------------------------------
  if p_id_grup_send is not null then
    select g.* into v_grup from public.groups g where g.id = p_id_grup_send;

    if not found then
      raise exception 'GRUP_INEXISTENT' using detail = 'Grupul nu exista.';
    end if;

    if not exists (
      select 1 from public.groups_participants gp
       where gp.id_group = v_grup.id and gp.id_user = p_id_user
    ) then
      raise exception 'NU_ESTI_MEMBRU' using detail = 'Nu faci parte din acest grup.';
    end if;

    perform 1 from public.groups g where g.id = v_grup.id for update;
    select g.* into v_grup from public.groups g where g.id = v_grup.id;

    -- Acelasi drept si acelasi plafon ca la plata obisnuita
    -- (0053_drepturi_grup.sql): banii pleaca din grup si pe drumul asta, chiar
    -- daca raman in asteptare, deci se verifica inainte de a-i scoate si se
    -- numara in cheltuiala lunii.
    perform public.verifica_drept_cheltuiala_grup(v_grup.id, p_id_user, v_suma);

    if v_grup.sold < v_suma then
      raise exception 'FONDURI_INSUFICIENTE_GRUP'
        using detail = format('Soldul grupului: %s RON, suma ceruta: %s RON.',
                              v_grup.sold, v_suma);
    end if;

    update public.groups set sold = sold - v_suma, modificat_la = now()
     where id = v_grup.id;

    -- Soldul comun scade sub ochii tuturor membrilor; le spunem de ce. Mesajul
    -- de tip „plata" se scrie abia daca administratorul accepta, ca sa nu apara
    -- in conversatie o plata care poate fi anulata.
    insert into public.group_messages (continut, id_user, id_group, type)
    values (
      format('%s RON au fost reținuți pentru verificare de către bancă.',
             public.formateaza_suma_ron(v_suma)),
      p_id_user, v_grup.id, 'text'
    );

    insert into public.tranzactii (
      id_user_send, id_group_send, id_user_recieve, id_cont_recieve,
      suma, valuta, descriere, status, motiv_semnalare
    )
    values (
      p_id_user, v_grup.id, v_recv.id_user, v_recv.id,
      v_suma, 'RON', nullif(btrim(coalesce(p_descriere, '')), ''), 'flagged', v_motiv
    )
    returning * into v_tranz;
  else
    if p_id_cont_send is not null then
      select c.id into v_id_send
        from public.conturi_bancare c
       where c.id = p_id_cont_send and c.id_user = p_id_user;

      if v_id_send is null then
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
       where c.id_user = p_id_user
       order by c.creat_la, c.id
       limit 1;

      if v_id_send is null then
        raise exception 'CONT_SURSA_INEXISTENT'
          using detail = 'Nu ai niciun cont din care sa platesti.';
      end if;
    end if;

    if v_id_send = v_recv.id then
      raise exception 'AUTOTRANSFER'
        using detail = 'Nu poti trimite bani in acelasi cont din care platesti.';
    end if;

    -- Se atinge un singur cont (beneficiarul nu e creditat aici), deci un
    -- singur lock — n-are cum sa apara ordinea incrucisata din `core_banking`.
    perform 1 from public.conturi_bancare c where c.id = v_id_send for update;
    select c.* into v_send from public.conturi_bancare c where c.id = v_id_send;

    if v_send.sold < v_suma then
      raise exception 'FONDURI_INSUFICIENTE'
        using detail = format('Sold disponibil: %s %s, suma ceruta: %s %s.',
                              v_send.sold, v_send.valuta, v_suma, v_send.valuta);
    end if;

    -- Triggerul din 0030 opreste aici transferul dintr-un cont blocat.
    update public.conturi_bancare set sold = sold - v_suma, modificat_la = now()
     where id = v_send.id;

    insert into public.tranzactii (
      id_user_send, id_user_recieve, id_cont_send, id_cont_recieve,
      suma, valuta, descriere, status, motiv_semnalare
    )
    values (
      p_id_user, v_recv.id_user, v_send.id, v_recv.id,
      v_suma, v_send.valuta, nullif(btrim(coalesce(p_descriere, '')), ''), 'flagged', v_motiv
    )
    returning * into v_tranz;
  end if;

  return jsonb_build_object(
    'id_tranzactie', v_tranz.id,
    'status',        v_tranz.status,
    'suma',          v_tranz.suma,
    'valuta',        v_tranz.valuta,
    'motiv',         v_motiv
  );
end;
$function$;


-- -----------------------------------------------------------------------------
-- 4. Ce vede si ce schimba creatorul
-- -----------------------------------------------------------------------------

/**
 * Drepturile tuturor membrilor, plus cat a cheltuit fiecare luna asta.
 *
 * O vede orice membru, nu doar creatorul: intr-o punga comuna e corect sa stii
 * pe ce reguli esti (si care e restul plafonului tau) fara sa fie nevoie sa
 * incerci o plata ca sa afli. Numele si avatarul vin de acolo de unde le ia si
 * `membri_grup` — profiles ramane inchis in rest.
 */
create or replace function public.drepturi_membri_grup(p_id_group bigint)
 returns table(
   id_user uuid,
   nume text,
   avatar_url text,
   creat_la timestamp with time zone,
   este_creator boolean,
   poate_cheltui boolean,
   limita_lunara numeric,
   cheltuit_luna numeric
 )
 language sql
 stable security definer
 set search_path to ''
as $function$
  select gp.id_user,
         p.nume,
         p.avatar_url,
         gp.creat_la,
         g.id_creator = gp.id_user,
         gp.poate_cheltui,
         gp.limita_lunara,
         public.cheltuit_luna_grup(p_id_group, gp.id_user)
    from public.groups_participants gp
    join public.profiles p on p.id = gp.id_user
    join public.groups   g on g.id = gp.id_group
   where gp.id_group = p_id_group
     and public.este_membru_grup(p_id_group)
   order by gp.creat_la, gp.id;
$function$;

/**
 * Creatorul seteaza drepturile unui membru.
 *
 * Nu poate schimba drepturile pentru el insusi: creatorul e cel care plateste
 * pentru grup cand nu mai poate nimeni altcineva, si un plafon pus din greseala
 * pe propriul rand n-ar mai avea cine sa-l ridice.
 */
create or replace function public.seteaza_drepturi_membru_grup(
  p_id_group      bigint,
  p_id_membru     uuid,
  p_poate_cheltui boolean,
  p_limita_lunara numeric default null
)
 returns jsonb
 language plpgsql
 security definer
 set search_path to ''
as $function$
declare
  v_user       uuid := auth.uid();
  v_id_creator uuid;
  v_limita     numeric(14,2);
begin
  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat.';
  end if;

  select g.id_creator into v_id_creator from public.groups g where g.id = p_id_group;

  if v_id_creator is null then
    raise exception 'GRUP_INEXISTENT'
      using detail = 'Nu exista acest grup.';
  end if;

  if v_id_creator <> v_user then
    raise exception 'NU_ESTI_CREATORUL'
      using detail = 'Doar creatorul grupului poate seta drepturile membrilor.';
  end if;

  if p_id_membru = v_user then
    raise exception 'NU_ITI_POTI_SETA_DREPTURILE'
      using detail = 'Creatorul grupului nu isi poate limita propriile drepturi.';
  end if;

  if p_poate_cheltui is null then
    raise exception 'DREPT_INVALID'
      using detail = 'Spune daca membrul poate sau nu sa cheltuiasca.';
  end if;

  v_limita := case when p_limita_lunara is null then null else round(p_limita_lunara, 2) end;

  if v_limita is not null and v_limita <= 0 then
    raise exception 'LIMITA_INVALIDA'
      using detail = 'Plafonul lunar trebuie sa fie mai mare decat 0.';
  end if;

  update public.groups_participants
     set poate_cheltui = p_poate_cheltui,
         -- Plafonul se sterge odata cu dreptul: cand membrul nu mai poate
         -- cheltui deloc, o cifra ramasa in camp ar induce in eroare la
         -- urmatoarea deschidere a drawerului.
         limita_lunara = case when p_poate_cheltui then v_limita else null end
   where id_group = p_id_group
     and id_user  = p_id_membru;

  if not found then
    raise exception 'NU_ESTE_MEMBRU'
      using detail = 'Persoana nu face parte din grup.';
  end if;

  return jsonb_build_object(
    'id_group',      p_id_group,
    'id_membru',     p_id_membru,
    'poate_cheltui', p_poate_cheltui,
    'limita_lunara', case when p_poate_cheltui then v_limita else null end
  );
end;
$function$;

/** Creatorul porneste sau opreste vizibilitatea miscarilor de bani intre membri. */
create or replace function public.seteaza_vizibilitate_tranzactii_grup(
  p_id_group bigint,
  p_vizibile boolean
)
 returns jsonb
 language plpgsql
 security definer
 set search_path to ''
as $function$
declare
  v_user       uuid := auth.uid();
  v_id_creator uuid;
begin
  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat.';
  end if;

  select g.id_creator into v_id_creator from public.groups g where g.id = p_id_group;

  if v_id_creator is null then
    raise exception 'GRUP_INEXISTENT'
      using detail = 'Nu exista acest grup.';
  end if;

  if v_id_creator <> v_user then
    raise exception 'NU_ESTI_CREATORUL'
      using detail = 'Doar creatorul grupului poate schimba vizibilitatea tranzactiilor.';
  end if;

  if p_vizibile is null then
    raise exception 'DREPT_INVALID'
      using detail = 'Spune daca tranzactiile se vad sau nu.';
  end if;

  update public.groups
     set tranzactii_vizibile = p_vizibile,
         modificat_la = now()
   where id = p_id_group;

  return jsonb_build_object('id_group', p_id_group, 'tranzactii_vizibile', p_vizibile);
end;
$function$;


-- -----------------------------------------------------------------------------
-- 5. Vizibilitatea anunturilor de bani din conversatie
-- -----------------------------------------------------------------------------
--
-- Politica veche lasa orice membru sa vada orice mesaj din grup. Acum
-- anunturile generate de functiile de bani (`incasare` / `plata`) se ascund
-- cand comutatorul e oprit — cu doua exceptii care raman mereu vizibile:
-- propriile miscari (nu te ascunzi de tine) si tot ce vede creatorul.
-- Mesajele scrise de oameni (`text`) nu sunt atinse: comutatorul e despre bani,
-- nu despre conversatie.

drop policy if exists "mesaje: select" on public.group_messages;

create policy "mesaje: select" on public.group_messages
  for select
  using (
    public.este_membru_grup(id_group)
    and (
      type = 'text'
      or id_user = auth.uid()
      or public.vede_tranzactiile_grupului(id_group)
    )
  );

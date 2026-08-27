-- =============================================================================
-- 0049 — Plata cu cardul vede poprirea, si esueaza curat
--
-- Gaura apare la intalnirea a doua schimbari facute in paralel, si nu se vede in
-- niciuna dintre ele citita singura:
--
--   0046 (main)   — plata verifica soldul DUPA autorizare, si isi ia un
--                   angajament explicit: „Esecurile ies ca FAILED cu motiv, nu ca
--                   exceptie". Verificarea e `v_cont.sold < v_in_cont`.
--   0047 (aici)   — o poprire face o parte din sold indisponibila, si un trigger
--                   refuza orice iesire care ar cobori sub suma poprita.
--
-- Puse cap la cap: un om cu 1000 lei in cont, din care 800 popriti, care plateste
-- 500 cu cardul. `v_cont.sold < v_in_cont` e fals (1000 > 500), deci verificarea
-- trece si se ajunge la `update conturi_bancare`. Acolo trigger-ul ridica
-- POPRIRE_ACTIVA — o EXCEPTIE, care da inapoi toata tranzactia, inclusiv
-- `plata_finalizeaza`. Rezultatul: plata nu se inchide nici in FAILED, magazinul
-- nu primeste nimic pe canalul platii, iar posesorul vede un cod brut in loc de
-- un motiv. Exact ce promitea 0046 ca nu se mai intampla.
--
-- Reparatia e o verificare in plus, inaintea debitarii, care OGLINDESTE trigger-ul
-- din 0047 in loc sa-l duplice pe jumatate: aceeasi formula, `least(disponibil,
-- rest_de_plata)`. Daca cele doua ar devia vreodata, trigger-ul ramane cel care
-- decide — asta de aici doar transforma un refuz sigur intr-un mesaj citibil.
--
-- Interogarile sunt scrise pe loc, nu prin `poprire_rest_de_plata` /
-- `poprire_disponibil_total`: alea sunt `security definer` si revocate pentru
-- oricine in afara de service_role, iar `aproba_plata` e `security invoker`. Cum
-- poprirea si conturile citite aici sunt ale platitorului insusi, politicile RLS
-- il lasa sa le vada — deci nu e nevoie nici de drepturi in plus, nici de o
-- schimbare a modului in care ruleaza functia.
--
-- Restul corpului e identic cu 0046.
-- =============================================================================

create or replace function public.aproba_plata(p_id uuid, p_id_user uuid)
returns public.payments
language plpgsql
volatile
set search_path = ''
as $$
declare
  v_plata        public.payments%rowtype;
  v_card         public.carduri%rowtype;
  v_cont         public.conturi_bancare%rowtype;
  v_in_cont      numeric(14,2);
  v_cheltuit_azi numeric(14,2);
  v_ramas        numeric(14,2);
  v_disponibil   numeric(14,2);
  v_in_ron       numeric(14,2);
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

  if not found then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Cardul nu mai exista.');
  end if;

  if v_card.blocat_administrativ then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Cardul a fost blocat de banca.');
  end if;

  if v_card.is_blocked then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Cardul este blocat din aplicatie.');
  end if;

  if public.card_expira_la(v_card.data_expirare) < current_date then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Cardul a expirat.');
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

  if v_cont.blocat_administrativ then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Contul cardului este blocat de banca.');
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

  -- NOU fata de 0046: banii popriti nu sunt bani disponibili.
  --
  -- Se calculeaza pe TOATE conturile omului, nu doar pe cel al cardului, fiindca
  -- asa lucreaza si poprirea (0047): ea sta pe client, nu pe cont.
  select coalesce(sum(p.suma_totala - p.suma_incasata), 0) into v_ramas
  from public.popriri p
  where p.id_utilizator = v_cont.id_user
    and p.status = 'activa';

  if v_ramas > 0 then
    select coalesce(sum(public.converteste(c.sold, c.valuta, 'RON')), 0) into v_disponibil
    from public.conturi_bancare c
    where c.id_user = v_cont.id_user
      and c.inchis_la is null;

    v_in_ron := public.converteste(v_in_cont, v_cont.valuta, 'RON');

    -- Aceeasi formula ca in trigger: cine are mai putin decat suma poprita are
    -- tot ce are indisponibil.
    if v_disponibil - v_in_ron < least(v_disponibil, v_ramas) then
      return public.plata_finalizeaza(
        v_plata.id, 'FAILED',
        'O parte din bani sunt indisponibili printr-o poprire.'
      );
    end if;
  end if;

  if v_card.limita_zilnica is not null then
    select coalesce(sum(t.suma), 0) into v_cheltuit_azi
      from public.tranzactii t
     where t.id_card_send = v_card.id
       and t.creat_la >= date_trunc('day', now());

    if v_cheltuit_azi + v_in_cont > v_card.limita_zilnica then
      return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Plata ar depasi limita zilnica a cardului.');
    end if;
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
  'Confirma o plata autorizata de posesor: verifica atunci cardul, contul, soldul, '
  'poprirea si limita zilnica, debiteaza si scrie tranzactia, totul atomic. '
  'Esecurile ies ca FAILED cu motiv, nu ca exceptie.';

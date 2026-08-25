-- =============================================================================
-- 0032 — Blocarea unui card de catre banca, pe care clientul n-o poate ridica
--
-- Pana acum cardul avea un singur steag, `is_blocked`, folosit si de client
-- (card pierdut) si — inainte de 0030 — de administrator. Cine bloca nu se mai
-- putea deosebi de cine deblocheaza: clientul apasa "Deblocheaza" si ridica
-- linistit masura bancii.
--
-- Nu se poate rezolva din drepturi: si actiunea clientului, si cea a
-- administratorului scriu cu `service_role`, deci baza le vede la fel. Solutia
-- e ca masurile sa fie doua lucruri diferite, nu acelasi steag disputat.
--
--   carduri.is_blocked            clientul; si-l pune si si-l scoate cand vrea
--   carduri.blocat_administrativ  banca; clientul nu-l atinge
--
-- Cardul e utilizabil doar cand AMANDOUA sunt false. Asa clientul isi poate
-- debloca in continuare propriul card fara sa ceara voie, dar deblocarea lui nu
-- mai anuleaza nimic din ce a hotarat banca.
-- =============================================================================

alter table public.carduri
  add column if not exists blocat_administrativ boolean not null default false;

comment on column public.carduri.blocat_administrativ is
  'Oprit de banca. Clientul nu il poate ridica; se ridica doar din panoul de administrare.';

comment on column public.carduri.is_blocked is
  'Blocat de client (card pierdut, precautie). Nu are efect asupra masurii bancii.';

create index if not exists carduri_blocat_administrativ_idx
  on public.carduri (id_user)
  where blocat_administrativ;


-- -----------------------------------------------------------------------------
-- Plata verifica ambele steaguri
--
-- Restul functiei ramane neatins fata de 0031. Se schimba doar conditia de
-- blocare si mesajul, ca omul sa afle cine a blocat cardul — de la banca se
-- rezolva altfel decat de la el.
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
  v_card         public.carduri%rowtype;
  v_cont         public.conturi_bancare%rowtype;
  v_plata        public.payments%rowtype;
  v_numar        text          := regexp_replace(coalesce(p_numar_card, ''), '\D', '', 'g');
  v_suma         numeric(14,2) := round(coalesce(p_suma, 0), 2);
  v_in_cont      numeric(14,2);
  v_cheltuit_azi numeric(14,2);
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

  if v_card.blocat_administrativ then
    raise exception 'CARD_BLOCAT_DE_BANCA'
      using detail = 'Cardul a fost blocat de banca si nu poate fi deblocat din aplicatie.';
  end if;

  if v_card.is_blocked then
    raise exception 'CARD_BLOCAT' using detail = 'Cardul este blocat din aplicatie.';
  end if;

  if public.card_expira_la(v_card.data_expirare) < current_date then
    raise exception 'CARD_EXPIRAT' using detail = 'Cardul a expirat.';
  end if;

  -- Contul cardului. Un singur cont, cel legat la emitere.
  select b.* into v_cont
  from public.conturi_bancare b
  where b.id = v_card.id_cont;

  if not found then
    raise exception 'FARA_CONT'
      using detail = 'Contul acestui card nu mai exista.';
  end if;

  if v_cont.blocat_administrativ then
    raise exception 'CONT_BLOCAT'
      using detail = 'Contul este blocat de banca; banii nu pot iesi din el.';
  end if;

  v_in_cont := public.converteste(v_suma, p_valuta, v_cont.valuta);

  if v_cont.sold < v_in_cont then
    raise exception 'FONDURI_INSUFICIENTE'
      using detail = 'Contul acestui card nu acopera suma platii.';
  end if;

  if v_card.limita_zilnica is not null then
    select coalesce(sum(t.suma), 0) into v_cheltuit_azi
      from public.tranzactii t
     where t.id_card_send = v_card.id
       and t.creat_la >= date_trunc('day', now());

    if v_cheltuit_azi + v_in_cont > v_card.limita_zilnica then
      raise exception 'LIMITA_DEPASITA'
        using detail = 'Plata ar depasi limita zilnica a cardului.';
    end if;
  end if;

  insert into public.payments (
    id_user, id_card, id_cont, card_ultimele4,
    suma, valuta, comerciant, descriere, status, expira_la
  )
  values (
    p_id_user, v_card.id, v_cont.id, right(v_card.numar_card, 4),
    v_suma, p_valuta, p_comerciant, p_descriere, 'PENDING_APPROVAL',
    now() + make_interval(secs => greatest(coalesce(p_secunde, 120), 30))
  )
  returning * into v_plata;

  return v_plata;
end;
$$;

revoke all on function public.creeaza_plata(uuid, text, text, text, numeric, text, text, text, integer) from public, anon, authenticated;
grant execute on function public.creeaza_plata(uuid, text, text, text, numeric, text, text, text, integer) to service_role;


-- -----------------------------------------------------------------------------
-- `aproba_plata` verifica si ea ambele steaguri
--
-- Fereastra e reala: plata se creeaza, banca blocheaza cardul sau contul, apoi
-- omul apasa "Confirma". Fara verificarea de aici plata ar trece pe ceva blocat
-- intre timp.
--
-- Corpul e cel din 0014_payments.sql, neatins in rest — inclusiv numele
-- parametrului `p_id`, cu care il cheama services/plati.ts. Se adauga doua
-- conditii: al doilea steag pe card, si steagul contului.
--
-- Contul e verificat explicit desi triggerul din 0030 l-ar opri oricum: acolo
-- ar iesi o exceptie care rupe tranzactia, aici plata primeste un FAILED curat,
-- cu motiv scris, pe care clientul il poate citi.
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

  if not found or v_card.is_blocked or v_card.blocat_administrativ then
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

  if v_cont.blocat_administrativ then
    return public.plata_finalizeaza(v_plata.id, 'FAILED', 'Contul este blocat de banca.');
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

revoke all on function public.aproba_plata(uuid, uuid) from public, anon, authenticated;
grant execute on function public.aproba_plata(uuid, uuid) to service_role;

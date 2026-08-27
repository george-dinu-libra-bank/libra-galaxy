-- =============================================================================
-- 0046 — intai autorizarea posesorului, apoi verificarea cardului si a soldului
--
-- Pana acum `creeaza_plata` verifica tot inainte sa intrebe pe cineva: cardul
-- blocat, cardul expirat, contul lipsa sau blocat, soldul, limita zilnica. Abia
-- daca toate treceau se nastea plata in PENDING_APPROVAL si pleca intrebarea
-- catre posesor. Efectul: magazinul afla starea cardului si a contului fara ca
-- posesorul sa fi autorizat nimic — „fonduri insuficiente" e un raspuns despre
-- omul din spatele cardului, dat cuiva care abia a tastat un numar de card.
--
-- Ordinea se inverseaza:
--
--   1. creare      -> cine e posesorul (numar + expirare + CVV) si atat;
--   2. autorizare  -> posesorul apasa „Confirma" in aplicatie;
--   3. verificare  -> card, cont, sold, limita — toate in `aproba_plata`,
--                     in aceeasi tranzactie cu debitarea.
--
-- Cautarea cardului ramane la creare fiindca nu e o verificare, ci singurul mod
-- de a sti pe cine intrebam: fara ea plata n-ar avea `id_user`. Restul, tot ce
-- spune ceva despre starea cardului sau a contului, se muta dupa semnatura.
--
-- Ce se schimba pentru magazin: motivele astea nu mai vin ca eroare sincrona la
-- POST /api/payments, ci ca plata terminata in FAILED, cu `motiv`, pe canalul
-- `plata:<id>` (0035). Ecranul de checkout stia deja sa afiseze starea aia.
--
-- Ce se schimba pentru posesor: primeste cererea de autorizare si pentru un card
-- blocat sau un cont fara bani. E de dorit — asa afla ca s-a incercat o plata cu
-- cardul lui, in loc ca incercarea sa fie oprita in tacere.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Creare — doar cine plateste, nimic despre starea lui
--
-- Semnatura ramane cea din 0035, deci `create or replace` e de ajuns si
-- drepturile date acolo raman valabile.
--
-- Un card inexistent si un CVV gresit primesc in continuare acelasi raspuns:
-- altfel formularul de checkout devine un oracol prin care se pot ghici, cifra
-- cu cifra, date de card valide.
-- -----------------------------------------------------------------------------
create or replace function public.creeaza_plata(
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
  v_card  public.carduri%rowtype;
  v_plata public.payments%rowtype;
  v_numar text          := regexp_replace(coalesce(p_numar_card, ''), '\D', '', 'g');
  v_suma  numeric(14,2) := round(coalesce(p_suma, 0), 2);
begin
  if v_suma <= 0 then
    raise exception 'SUMA_INVALIDA' using detail = 'Suma platii trebuie sa fie strict pozitiva.';
  end if;

  if coalesce(p_valuta, '') !~ '^[A-Z]{3}$' then
    raise exception 'VALUTA_NESUPORTATA' using detail = 'Valuta platii trebuie sa fie un cod ISO de trei litere.';
  end if;

  -- `numar_card` e unique (0002_carduri_tranzactii.sql), deci cautarea intoarce
  -- cel mult un rand.
  select c.* into v_card
  from public.carduri c
  where c.numar_card = v_numar;

  if not found
     or v_card.data_expirare is distinct from p_data_expirare
     or v_card.ccv is distinct from p_ccv
  then
    raise exception 'DATE_CARD_GRESITE'
      using detail = 'Numarul, data de expirare sau CVV-ul nu corespund niciunui card.';
  end if;

  -- Contul cardului se retine asa cum e acum, fara sa fie judecat: daca intre
  -- timp dispare sau se blocheaza, `aproba_plata` inchide plata in FAILED.
  insert into public.payments (
    id_user, id_card, id_cont, card_ultimele4,
    suma, valuta, comerciant, descriere, status, expira_la
  )
  values (
    v_card.id_user, v_card.id, v_card.id_cont, right(v_card.numar_card, 4),
    v_suma, p_valuta, p_comerciant, p_descriere, 'PENDING_APPROVAL',
    now() + make_interval(secs => greatest(coalesce(p_secunde, 120), 30))
  )
  returning * into v_plata;

  return v_plata;
end;
$$;

comment on function public.creeaza_plata is
  'Gaseste cardul dupa numar/expirare/CVV si deschide o plata in PENDING_APPROVAL pe numele posesorului. Nu verifica starea cardului, a contului sau soldul — alea se verifica in aproba_plata, dupa autorizare. Nu misca bani si nu stocheaza CVV-ul.';


-- -----------------------------------------------------------------------------
-- 2. Aprobare — aici se verifica tot, cu locks si in aceeasi tranzactie
--
-- Corpul e cel din 0014_payments.sql, cu trei verificari in plus, mutate din
-- `creeaza_plata`: cardul blocat de banca, contul blocat de banca si limita
-- zilnica a cardului. Fara ele, dupa mutarea de mai sus n-ar mai fi verificate
-- nicaieri.
--
-- Toate esecurile trec prin `plata_finalizeaza`, deci magazinul primeste
-- FAILED plus motivul pe canalul platii, nu o eroare fara explicatie.
-- -----------------------------------------------------------------------------
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
  'Confirma o plata autorizata de posesor: verifica atunci cardul, contul, soldul si limita zilnica, debiteaza si scrie tranzactia, totul atomic. Esecurile ies ca FAILED cu motiv, nu ca exceptie.';

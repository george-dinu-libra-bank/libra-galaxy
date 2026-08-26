-- =============================================================================
-- 0035 — plata din magazin se leaga de card, nu de sesiunea celui care plateste
--
-- Pana acum `creeaza_plata` primea `p_id_user` (utilizatorul logat in magazin)
-- si cauta cardul cu `numar_card = ... and id_user = p_id_user`. Adica puteai
-- plati doar cu propriul card, doar logat — ceea ce nu seamana cu o plata reala:
-- la un procesator adevarat, cine plateste da doar datele cardului, iar banca
-- decide singura cine e posesorul si pe cine intreaba.
--
-- Aici cardul devine singura identitate a platii:
--
--   numar + expirare + CVV  ->  carduri.id_user  ->  payments.id_user
--
-- Restul lantului nu se schimba deloc, fiindca era deja scris in termeni de
-- „posesorul randului", nu de „cel care a deschis plata": `aproba_plata` si
-- `respinge_plata` cer in continuare `p_id_user` si verifica proprietarul, RLS-ul
-- pe payments ramane `auth.uid() = id_user`, iar coada de confirmare din
-- aplicatie asculta Realtime filtrat pe `id_user`. Cererea de autorizare ajunge
-- deci la posesorul cardului, fara nicio linie in plus.
--
-- Ce trebuie insa rezolvat explicit: magazinul nu mai are voie sa citeasca randul
-- (nu mai e `id_user`), deci nu mai poate afla prin `postgres_changes` cum s-a
-- terminat plata. Pentru asta apare `anunta_plata` — un broadcast pe un topic
-- ne-privat, numit dupa id-ul platii (sectiunea 2).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Creare — cardul spune cine plateste
--
-- Parametrul `p_id_user` iese din semnatura, deci `create or replace` nu ajunge:
-- se sterge intai vechea functie. Nu se lasa cele doua variante in paralel —
-- PostgREST le apeleaza pe nume si alegerea ar deveni ambigua.
-- -----------------------------------------------------------------------------
drop function if exists public.creeaza_plata(uuid, text, text, text, numeric, text, text, text, integer);

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
  v_card         public.carduri%rowtype;
  v_cont         public.conturi_bancare%rowtype;
  v_plata        public.payments%rowtype;
  v_numar        text          := regexp_replace(coalesce(p_numar_card, ''), '\D', '', 'g');
  v_suma         numeric(14,2) := round(coalesce(p_suma, 0), 2);
  v_in_cont      numeric(14,2);
  v_cheltuit_azi numeric(14,2);
begin
  if v_suma <= 0 then
    raise exception 'SUMA_INVALIDA' using detail = 'Suma platii trebuie sa fie strict pozitiva.';
  end if;

  if coalesce(p_valuta, '') !~ '^[A-Z]{3}$' then
    raise exception 'VALUTA_NESUPORTATA' using detail = 'Valuta platii trebuie sa fie un cod ISO de trei litere.';
  end if;

  -- `numar_card` e unique (0002_carduri_tranzactii.sql), deci cautarea intoarce
  -- cel mult un rand. Un card inexistent si un CVV gresit primesc in continuare
  -- acelasi raspuns: altfel formularul de checkout devine un oracol prin care se
  -- pot ghici, cifra cu cifra, date de card valide.
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

  -- Plata se scrie pe posesorul cardului. El e cel intrebat, el plateste.
  insert into public.payments (
    id_user, id_card, id_cont, card_ultimele4,
    suma, valuta, comerciant, descriere, status, expira_la
  )
  values (
    v_card.id_user, v_card.id, v_cont.id, right(v_card.numar_card, 4),
    v_suma, p_valuta, p_comerciant, p_descriere, 'PENDING_APPROVAL',
    now() + make_interval(secs => greatest(coalesce(p_secunde, 120), 30))
  )
  returning * into v_plata;

  return v_plata;
end;
$$;

comment on function public.creeaza_plata is
  'Gaseste cardul dupa numar/expirare/CVV si deschide o plata in PENDING_APPROVAL pe numele posesorului. Nu misca bani si nu stocheaza CVV-ul.';

comment on column public.payments.id_user is
  'Posesorul cardului — cel care autorizeaza plata si din al carui cont ies banii; nu neaparat cine a initiat-o din magazin.';

revoke all on function public.creeaza_plata(text, text, text, numeric, text, text, text, integer)
  from public, anon, authenticated;
grant execute on function public.creeaza_plata(text, text, text, numeric, text, text, text, integer)
  to service_role;


-- -----------------------------------------------------------------------------
-- 2. Raspunsul catre magazin — broadcast pe un topic numit dupa plata
--
-- Ecranul de checkout asculta pana acum `postgres_changes` pe payments, filtrat
-- pe `id`. Asta mergea doar fiindca plata era, prin definitie, a celui logat in
-- magazin: RLS-ul (`auth.uid() = id_user`) ii dadea voie sa vada randul. Acum
-- cumparatorul poate fi altcineva, sau nimeni — abonarea ar primi CHANNEL_ERROR,
-- iar ecranul ar ramane pe „se asteapta confirmarea" pana la expirare, orice ar
-- apasa posesorul.
--
-- Solutia nu e sa largim RLS-ul (n-avem pe cine sa largim: cumparatorul e
-- anonim), ci sa trimitem starea pe un canal la care nu e nevoie de identitate.
-- Topicul e `plata:<uuid>`, iar ultimul argument al lui `realtime.send` e FALSE,
-- adica ne-privat: nu se verifica nicio politica la abonare. Ce tine plata
-- secreta e ca `id`-ul ei e un UUID aleator, dat o singura data, celui care a
-- initiat plata.
--
-- Se trimit doar `status` si `motiv`. Nici suma, nici cardul, nici posesorul —
-- topicul e public, deci in el nu are ce cauta nimic despre om.
--
-- Forma e cea a lui `anunta_utilizator` (0000, liniile 24-42), inclusiv
-- inghitirea erorii: o plata nu trebuie sa pice fiindca Realtime a cazut.
-- -----------------------------------------------------------------------------
create or replace function public.anunta_plata(p_id uuid, p_status text, p_motiv text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_id is null then
    return;
  end if;

  begin
    perform realtime.send(
      jsonb_build_object('id', p_id, 'status', p_status, 'motiv', p_motiv),
      'stare',
      'plata:' || p_id::text,
      false
    );
  exception when others then
    raise warning 'REALTIME_ESUAT (plata=%, status=%): %', p_id, p_status, sqlerrm;
  end;
end;
$$;

comment on function public.anunta_plata is
  'Trimite starea finala a unei plati pe topicul public plata:<id>, pentru ecranul de checkout al comerciantului.';

-- Nu se da nimanui in afara de service_role: altfel oricine ar putea emite prin
-- RPC un „APPROVED" fals catre magazin, fara ca plata sa se fi intamplat.
revoke all on function public.anunta_plata(uuid, text, text) from public, anon, authenticated;
grant execute on function public.anunta_plata(uuid, text, text) to service_role;


-- -----------------------------------------------------------------------------
-- 3. Anuntul pleaca din singurul loc prin care trec toate starile finale
--
-- Corpul e cel din 0014_payments.sql, neatins in rest. `plata_finalizeaza` e
-- pusa in mijloc de `aproba_plata` (APPROVED, EXPIRED, FAILED) si de
-- `respinge_plata` (DECLINED), deci un singur carlig aici acopera tot fluxul —
-- nu e nevoie sa atingem functiile de aprobare/respingere.
--
-- `realtime.send` scrie tranzactional, deci mesajul pleaca abia dupa commit:
-- magazinul nu poate afla „APPROVED" inaintea debitarii contului.
--
-- Se anunta si cand update-ul n-a prins randul (altcineva a finalizat primul):
-- starea trimisa e tot cea reala, iar ecranul o primeste de doua ori cel mult,
-- ceea ce nu-l deranjeaza.
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

  perform public.anunta_plata(v_plata.id, v_plata.status, v_plata.motiv);

  return v_plata;
end;
$$;

revoke all on function public.plata_finalizeaza(uuid, text, text) from public, anon, authenticated;
grant execute on function public.plata_finalizeaza(uuid, text, text) to service_role;

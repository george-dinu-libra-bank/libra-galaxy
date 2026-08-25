-- =============================================================================
-- 0029 — Pasul C: contul devine obligatoriu, iar plata il foloseste
--
-- Se ruleaza DUPA ce 0028 a raportat `carduri_fara_cont = 0`.
--
-- Daca a ramas vreun card fara cont, `set not null` esueaza si nimic nu se
-- aplica. E comportamentul dorit: un card orfan trebuie rezolvat, nu ascuns.
-- =============================================================================

alter table public.carduri
  alter column id_cont set not null;


-- -----------------------------------------------------------------------------
-- `creeaza_plata` — contul vine de la card, nu dintr-o scanare
--
-- Inainte, functia parcurgea TOATE conturile utilizatorului si il lua pe primul
-- care acoperea suma. Cardul nu conta: doua carduri diferite ale aceluiasi om
-- debitau intotdeauna acelasi cont, iar un card putea goli un cont pe care
-- proprietarul il tinea deoparte.
--
-- Acum cardul e instrumentul unui cont anume. Restul functiei ramane neatins:
-- aceleasi verificari de card, aceeasi conversie prin `converteste`, aceleasi
-- coduri de eroare. Se schimba doar intelesul lui FONDURI_INSUFICIENTE — "contul
-- acestui card nu acopera suma", nu "niciun cont al tau nu o acopera".
--
-- CURS_INDISPONIBIL nu mai e inghitit. Inainte, un cont a carui valuta n-avea
-- curs BNR se sarea si se incerca urmatorul; acum nu mai exista "urmatorul", iar
-- a pretinde ca fondurile sunt insuficiente cand de fapt nu stim cursul ar fi un
-- raspuns gresit.
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

  -- Contul cardului. Un singur cont, cel legat la emitere.
  select b.* into v_cont
  from public.conturi_bancare b
  where b.id = v_card.id_cont;

  if not found then
    raise exception 'FARA_CONT'
      using detail = 'Contul acestui card nu mai exista.';
  end if;

  v_in_cont := public.converteste(v_suma, p_valuta, v_cont.valuta);

  if v_cont.sold < v_in_cont then
    raise exception 'FONDURI_INSUFICIENTE'
      using detail = 'Contul acestui card nu acopera suma platii.';
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

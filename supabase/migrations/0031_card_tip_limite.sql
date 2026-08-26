-- =============================================================================
-- 0031 — Carduri virtuale si limita zilnica
--
-- Amandoua devin posibile abia dupa 0029: un card are acum un cont propriu,
-- deci si o valuta proprie si un sold propriu. Inainte, "limita cardului" n-ar
-- fi avut in ce valuta sa fie exprimata, iar un card virtual n-ar fi avut pe ce
-- cont sa fie emis.
-- =============================================================================

alter table public.carduri
  add column if not exists tip text not null default 'fizic';

alter table public.carduri
  drop constraint if exists carduri_tip_check;

alter table public.carduri
  add constraint carduri_tip_check check (tip in ('fizic', 'virtual'));

comment on column public.carduri.tip is
  'fizic = card obisnuit; virtual = emis in aplicatie, pentru plati online.';


alter table public.carduri
  add column if not exists limita_zilnica numeric(14,2);

alter table public.carduri
  drop constraint if exists carduri_limita_check;

-- `null` = fara limita. Deliberat null si nu 0: un 0 ar insemna "nu poti plati
-- nimic", iar cele doua sunt usor de confundat intr-un formular gol.
alter table public.carduri
  add constraint carduri_limita_check
  check (limita_zilnica is null or limita_zilnica > 0);

comment on column public.carduri.limita_zilnica is
  'Cat poate cheltui cardul intr-o zi, in valuta contului. null = fara limita.';


-- Insumarea cheltuielilor de azi pe un card, la fiecare plata.
create index if not exists tranzactii_card_zi_idx
  on public.tranzactii (id_card_send, creat_la desc)
  where id_card_send is not null;


-- -----------------------------------------------------------------------------
-- `creeaza_plata` — aceeasi functie ca in 0029, plus verificarea limitei
--
-- Cheltuiala de azi se citeste din `tranzactii`, nu din `payments`: acolo ajung
-- doar platile chiar debitate, si sunt deja convertite in valuta contului de
-- `aproba_plata`. Insumarea platilor in asteptare ar fi refuzat bani pe care
-- omul poate nici nu-i cheltuie, daca lasa un checkout deschis.
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

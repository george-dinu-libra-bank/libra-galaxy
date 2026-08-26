-- =============================================================================
-- Libra — schimb valutar cu suma partiala, intr-un cont separat per valuta
--
-- Aditiva la schema din 0000_instantaneu_inainte_de_credite.sql
-- (public.schimba_valuta_cont, public.converteste, public.genereaza_iban).
--
-- public.schimba_valuta_cont convertea TOT soldul unui cont, in loc — util
-- doar daca vrei ca acel cont sa devina alta valuta. Functia de aici e pentru
-- schimbul de zi cu zi: o suma partiala trece dintr-un cont sursa intr-un cont
-- destinatie in noua valuta — creat automat daca utilizatorul nu are inca unul
-- in acea valuta, la fel ca la deschiderea manuala de cont (lib/actions/conturi.ts),
-- doar ca fara pas de confirmare separat. Cele doua functii coexista;
-- schimba_valuta_cont ramane pentru cazul ei (schimbarea valutei unui cont).
-- =============================================================================

CREATE OR REPLACE FUNCTION public.schimba_valuta_suma(
  p_id_cont_sursa uuid,
  p_suma numeric,
  p_valuta_noua text,
  p_id_user uuid DEFAULT NULL::uuid
)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_user          uuid;
  v_este_srv      boolean := coalesce(auth.role(), 'service_role') = 'service_role';
  v_valuta        text := upper(btrim(coalesce(p_valuta_noua, '')));
  v_suma          numeric(14,2);
  v_sursa         public.conturi_bancare%rowtype;
  v_dest          public.conturi_bancare%rowtype;
  v_id_dest       uuid;
  v_primit        numeric(14,2);
  v_cont_nou      boolean := false;
  v_numar_conturi integer;
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

  -- ---------------------------------------------------------------------------
  -- Validari de format
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

  if v_valuta not in ('RON', 'EUR', 'USD', 'GBP', 'CHF') then
    raise exception 'VALUTA_NESUPORTATA'
      using detail = 'Se poate schimba doar in RON, EUR, USD, GBP sau CHF.';
  end if;

  -- ---------------------------------------------------------------------------
  -- Contul sursa trebuie sa fie al tau. Citire preliminara, fara lock: destul
  -- pentru validarile ieftine (valuta, sold aproximativ), ca sa nu cream un
  -- cont destinatie degeaba pentru o cerere clar invalida.
  -- ---------------------------------------------------------------------------
  select * into v_sursa from public.conturi_bancare c
   where c.id = p_id_cont_sursa and c.id_user = v_user;

  if v_sursa.id is null then
    if exists (select 1 from public.conturi_bancare c where c.id = p_id_cont_sursa) then
      raise exception 'CONT_STRAIN'
        using detail = 'Nu poti schimba valuta unui cont care nu e al tau.';
    end if;

    raise exception 'CONT_INEXISTENT'
      using detail = 'Contul nu exista.';
  end if;

  if v_sursa.valuta = v_valuta then
    raise exception 'ACEEASI_VALUTA'
      using detail = 'Contul e deja in aceasta valuta.';
  end if;

  if v_sursa.sold < v_suma then
    raise exception 'FONDURI_INSUFICIENTE'
      using detail = format('Sold disponibil: %s %s, suma ceruta: %s %s.',
                            v_sursa.sold, v_sursa.valuta, v_suma, v_sursa.valuta);
  end if;

  v_primit := public.converteste(v_suma, v_sursa.valuta, v_valuta);

  if v_primit <= 0 then
    raise exception 'SUMA_PREA_MICA'
      using detail = 'Suma e prea mica pentru a ajunge in noua valuta.';
  end if;

  -- ---------------------------------------------------------------------------
  -- Contul destinatie: cel existent in noua valuta, sau unul nou. Advisory
  -- lock pe utilizator, ca doua schimburi concurente in aceeasi valuta noua
  -- sa nu creeze doua conturi (unic doar pe iban, nu pe valuta).
  -- ---------------------------------------------------------------------------
  perform pg_advisory_xact_lock(hashtextextended(v_user::text, 0));

  select c.id into v_id_dest from public.conturi_bancare c
   where c.id_user = v_user and c.valuta = v_valuta
   order by c.creat_la
   limit 1;

  if v_id_dest is null then
    select count(*) into v_numar_conturi from public.conturi_bancare c where c.id_user = v_user;

    -- Acelasi plafon ca deschiderea manuala de cont (lib/actions/conturi.ts:MAX_CONTURI).
    if v_numar_conturi >= 10 then
      raise exception 'CONTURI_LIMITA'
        using detail = 'Poti avea cel mult 10 conturi.';
    end if;

    insert into public.conturi_bancare (id_user, nume, iban, valuta, sold)
    values (v_user, 'Cont ' || v_valuta, public.genereaza_iban(), v_valuta, 0)
    returning id into v_id_dest;

    v_cont_nou := true;
  end if;

  -- ---------------------------------------------------------------------------
  -- Blocam si re-validam sub lock, in ordinea id-ului (la fel ca
  -- public.core_banking) — intre citirea preliminara si acum s-ar fi putut
  -- strecura un alt schimb sau transfer din acelasi cont.
  -- ---------------------------------------------------------------------------
  if v_sursa.id < v_id_dest then
    perform 1 from public.conturi_bancare c where c.id = v_sursa.id for update;
    perform 1 from public.conturi_bancare c where c.id = v_id_dest for update;
  else
    perform 1 from public.conturi_bancare c where c.id = v_id_dest for update;
    perform 1 from public.conturi_bancare c where c.id = v_sursa.id for update;
  end if;

  select * into v_sursa from public.conturi_bancare c where c.id = v_sursa.id;
  select * into v_dest  from public.conturi_bancare c where c.id = v_id_dest;

  if v_sursa.valuta = v_dest.valuta then
    raise exception 'ACEEASI_VALUTA'
      using detail = 'Contul e deja in aceasta valuta.';
  end if;

  if v_sursa.sold < v_suma then
    raise exception 'FONDURI_INSUFICIENTE'
      using detail = format('Sold disponibil: %s %s, suma ceruta: %s %s.',
                            v_sursa.sold, v_sursa.valuta, v_suma, v_sursa.valuta);
  end if;

  v_primit := public.converteste(v_suma, v_sursa.valuta, v_dest.valuta);

  if v_primit <= 0 then
    raise exception 'SUMA_PREA_MICA'
      using detail = 'Suma e prea mica pentru a ajunge in noua valuta.';
  end if;

  -- ---------------------------------------------------------------------------
  -- Miscarea banilor
  -- ---------------------------------------------------------------------------
  update public.conturi_bancare set sold = sold - v_suma where id = v_sursa.id;
  update public.conturi_bancare set sold = sold + v_primit where id = v_dest.id;

  return jsonb_build_object(
    'id_cont_sursa',      v_sursa.id,
    'valuta_sursa',       v_sursa.valuta,
    'suma_schimbata',     v_suma,
    'id_cont_destinatie', v_dest.id,
    'valuta_destinatie',  v_dest.valuta,
    'suma_primita',       v_primit,
    'cont_nou',           v_cont_nou
  );
end;
$function$
;

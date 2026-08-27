-- =============================================================================
-- 0048 — Stornarea unei incasari din poprire: banii virati se intorc
--
-- 0047 avea o gaura de operare, scrisa chiar in comentariile ei: „banii deja
-- virati NU se intorc automat — au plecat catre creditor". Adevarat ca
-- descriere a lumii, dar inutilizabil ca unealta. O incasare gresita — suma
-- prea mare, poprire pusa pe omul gresit, contestatie admisa DUPA ce banca
-- virase — nu avea nicio cale de indreptare in aplicatie. Ramanea „sunati la
-- creditor", adica exact raspunsul pe care un client nu-l poate accepta cand
-- banca i-a luat banii din greseala.
--
-- Asta e operatiunea inversa lui `incaseaza_poprirea`. Nu inlocuieste
-- `ridica_poprirea`, sunt lucruri diferite si se folosesc adesea impreuna:
--
--   ridica_poprirea      — poprirea inceteaza. Banii ramasi in cont se
--                          elibereaza; cei deja virati raman plecati.
--   storneaza_incasarea  — banii virati se intorc in contul omului. Poprirea
--                          NU inceteaza prin asta.
--
-- O poprire pusa din greseala si deja incasata se repara cu amandoua, in ordinea
-- asta: intai stornarea (vin banii inapoi), apoi ridicarea (nu-i mai tine nimeni).
--
-- CONSECINTA CARE SURPRINDE, si e corecta: daca poprirea ramane activa dupa
-- stornare, banii intorsi sunt IMEDIAT indisponibili din nou — datoria a redevenit
-- neplatita, deci suma redevine poprita. Nu e un bug; e diferenta dintre „am
-- gresit virarea" si „poprirea n-ar fi trebuit sa existe". Scrie in notificare.
--
-- UNDE se intorc banii: in contul principal al omului, altfel in cel mai vechi
-- cont deschis. NU neaparat in conturile din care au plecat — acelea pot fi
-- inchise intre timp, iar banii sunt fungibili. Se scrie explicit in notificare,
-- ca omul sa nu-i caute in contul gresit.
-- =============================================================================

create or replace function public.storneaza_incasarea(
  p_id_poprire uuid,
  p_id_admin   uuid,
  p_suma       numeric default null,
  p_motiv      text default null
)
returns public.popriri
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_poprire   public.popriri%rowtype;
  v_max       numeric(14,2);
  v_suma      numeric(14,2);
  v_cont      public.conturi_bancare%rowtype;
  v_iban      text;
  v_in_cont   numeric(14,2);
  v_reactivat boolean := false;
  v_mesaj     text;
begin
  select p.* into v_poprire
  from public.popriri p
  where p.id = p_id_poprire
  for update;

  if not found then
    raise exception 'POPRIRE_INEXISTENTA' using detail = 'Poprirea nu exista.';
  end if;

  v_max := v_poprire.suma_incasata;

  if v_max <= 0 then
    raise exception 'NIMIC_DE_STORNAT'
      using detail = 'Din poprirea asta nu s-a virat nimic catre creditor.';
  end if;

  if p_suma is not null and round(p_suma, 2) > v_max then
    raise exception 'PESTE_SUMA_INCASATA'
      using detail = 'Din poprire s-au virat doar ' ||
                     trim(to_char(v_max, 'FM999999999990.00')) || ' RON.';
  end if;

  v_suma := coalesce(round(p_suma, 2), v_max);

  -- Destinatia: contul principal, altfel cel mai vechi deschis. Un cont blocat
  -- administrativ e o destinatie valida — 0030 opreste doar IESIRILE, iar banii
  -- omului trebuie sa se intoarca la el chiar daca are contul inghetat.
  select pr.iban_cont into v_iban
  from public.profiles pr where pr.id = v_poprire.id_utilizator;

  select c.* into v_cont
  from public.conturi_bancare c
  where c.id_user = v_poprire.id_utilizator
    and c.inchis_la is null
    and (v_iban is null or c.iban = v_iban)
  order by c.creat_la
  limit 1
  for update;

  if not found then
    select c.* into v_cont
    from public.conturi_bancare c
    where c.id_user = v_poprire.id_utilizator
      and c.inchis_la is null
    order by c.creat_la
    limit 1
    for update;
  end if;

  if not found then
    raise exception 'FARA_CONT_DESCHIS'
      using detail = 'Clientul nu mai are niciun cont deschis in care sa se intoarca banii.';
  end if;

  v_in_cont := public.converteste(v_suma, 'RON', v_cont.valuta);

  -- Bani care INTRA: trigger-ele din 0030 si 0047 lasa cresterile sa treaca, deci
  -- nu e nevoie de niciun steag de ocolire. Exact pe dos fata de incasare.
  update public.conturi_bancare c
     set sold = c.sold + v_in_cont, modificat_la = now()
   where c.id = v_cont.id;

  insert into public.tranzactii (
    id_user_recieve, id_cont_recieve, suma, valuta, descriere
  )
  values (
    v_poprire.id_utilizator, v_cont.id, v_in_cont, v_cont.valuta,
    'Stornare poprire — retur de la ' || v_poprire.creditor
  );

  -- O poprire stinsa care primeste banii inapoi nu mai e stinsa: datoria a
  -- redevenit neplatita. Una ridicata ramane ridicata — acolo decizia a fost ca
  -- poprirea nu mai are obiect, iar stornarea nu o reinvie.
  if v_poprire.status = 'stinsa' then
    v_reactivat := true;
  end if;

  update public.popriri p
     set suma_incasata = p.suma_incasata - v_suma,
         id_admin      = p_id_admin,
         status        = case when v_reactivat then 'activa' else p.status end,
         incheiat_la   = case when v_reactivat then null else p.incheiat_la end,
         observatie    = coalesce(nullif(trim(p_motiv), ''), p.observatie)
   where p.id = p_id_poprire
  returning * into v_poprire;

  v_mesaj := 'Am returnat in contul "' || v_cont.nume || '" suma de ' ||
             trim(to_char(v_in_cont, 'FM999999999990.00')) || ' ' || v_cont.valuta ||
             ', virata anterior catre ' || v_poprire.creditor || '.' ||
             coalesce(' ' || nullif(trim(p_motiv), ''), '');

  if v_poprire.status = 'activa' then
    -- Partea care surprinde, spusa direct: banii sunt din nou indisponibili.
    v_mesaj := v_mesaj || ' Poprirea ramane in vigoare, asa ca suma returnata ' ||
               'este din nou indisponibila pana la stingerea ei.';
  else
    v_mesaj := v_mesaj || ' Poprirea nu mai este in vigoare, deci banii sunt la ' ||
               'dispozitia ta.';
  end if;

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (
    v_poprire.id_utilizator,
    'Bani returnati dintr-o poprire',
    v_mesaj,
    case when v_poprire.status = 'activa' then 'info' else 'deblocare' end
  );

  perform public.anunta_utilizator(
    v_poprire.id_utilizator, 'notificare',
    jsonb_build_object('id_poprire', v_poprire.id, 'status', v_poprire.status)
  );

  return v_poprire;
end;
$$;

comment on function public.storneaza_incasarea(uuid, uuid, numeric, text) is
  'Aduce inapoi in contul clientului bani virati dintr-o poprire. Fara suma, '
  'storneaza tot ce s-a incasat. Nu ridica poprirea — aceea e ridica_poprirea.';

revoke all on function public.storneaza_incasarea(uuid, uuid, numeric, text)
  from public, anon, authenticated;
grant execute on function public.storneaza_incasarea(uuid, uuid, numeric, text) to service_role;

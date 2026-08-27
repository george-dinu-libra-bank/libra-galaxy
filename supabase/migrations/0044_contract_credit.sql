-- -----------------------------------------------------------------------------
-- Libra — contractul de credit
--
-- Pana acum "contractul" era o metafora: `credite` e numit contract in
-- comentarii, dar nu exista niciun document pe care clientul sa-l citeasca. Se
-- apasa "Semneaza" direct peste o oferta de trei cifre.
--
-- Fluxul nou are trei momente, si fiecare isi are coloana lui:
--
--   1. cererea se depune  -> analistul primeste un sablon completat din baza
--                            (`contract_html`, scris de backend la prima
--                            deschidere a dosarului);
--   2. analistul aproba   -> contractul pleaca la client (`contract_trimis_la`);
--   3. clientul semneaza  -> textul se ingheata intr-un PDF pus in
--                            `credit-documente`, iar calea lui ajunge in
--                            `credite.contract_url`.
--
-- De ce sta textul pe `credit_cereri` si nu pe `credite`: pana la semnatura nu
-- exista niciun rand in `credite`. Contractul apartine cererii cat timp e in
-- lucru si abia dupa semnatura devine documentul creditului.
-- -----------------------------------------------------------------------------

alter table public.credit_cereri
  add column if not exists contract_html          text,
  add column if not exists contract_actualizat_la timestamptz,
  add column if not exists contract_actualizat_de uuid references public.profiles(id),
  add column if not exists contract_trimis_la     timestamptz;

comment on column public.credit_cereri.contract_html is
  'Contractul pe care il editeaza analistul, in HTML restrans (vezi backend/app/credit/contract.py: ETICHETE_PERMISE). Sanitizat la scriere, niciodata randat neverificat.';

comment on column public.credit_cereri.contract_trimis_la is
  'Momentul in care contractul a plecat la client, odata cu oferta. Null = clientul nu l-a vazut inca.';

alter table public.credite
  add column if not exists contract_url text;

comment on column public.credite.contract_url is
  'Calea din bucket-ul privat `credit-documente` catre PDF-ul semnat, nu un URL public: bucket-ul e privat, deci linkul se semneaza la fiecare citire.';


-- -----------------------------------------------------------------------------
-- credit_acorda: primeste calea contractului si refuza semnatura fara el
--
-- Vechea semnatura se sterge, nu se lasa alaturi: cu `default null` pe
-- parametrul nou, cele doua functii ar fi ambigue pentru PostgREST.
-- -----------------------------------------------------------------------------
drop function if exists public.credit_acorda(uuid, uuid, numeric, numeric, jsonb, jsonb);

create or replace function public.credit_acorda(
  p_id_cerere   uuid,
  p_id_cont     uuid,
  p_rata_lunara numeric,
  p_dae         numeric,
  p_grafic      jsonb,
  p_semnatura   jsonb default '{}'::jsonb,
  p_contract_url text default null
)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $$
declare
  v_este_srv    boolean := coalesce(auth.role(), 'service_role') = 'service_role';
  v_cerere      public.credit_cereri%rowtype;
  v_cont        public.conturi_bancare%rowtype;
  v_credit      public.credite%rowtype;
  v_tranz       public.tranzactii%rowtype;
  v_suma_grafic numeric(14,2);
  v_numar_rate  integer;
begin
  -- Acordarea de credit se face numai din backend. Un client cu sesiune proprie
  -- nu are ce cauta aici nici macar pe cererea lui: decizia nu e a lui.
  if not v_este_srv then
    raise exception 'NEAUTORIZAT' using detail = 'Acordarea unui credit se face numai din serviciul bancii.';
  end if;

  select * into v_cerere from public.credit_cereri c where c.id = p_id_cerere for update;
  if not found then
    raise exception 'CERERE_INEXISTENTA' using detail = 'Cererea de credit nu exista.';
  end if;

  if v_cerere.status <> 'oferta' then
    raise exception 'CERERE_IN_STARE_GRESITA'
      using detail = format('Cererea e in starea "%s"; se poate accepta numai o cerere cu oferta.', v_cerere.status);
  end if;

  if v_cerere.oferta_expira_la is not null and v_cerere.oferta_expira_la < now() then
    raise exception 'OFERTA_EXPIRATA' using detail = 'Oferta a expirat; e nevoie de o cerere noua.';
  end if;

  if exists (select 1 from public.credite k where k.id_cerere = p_id_cerere) then
    raise exception 'CREDIT_DEJA_ACORDAT' using detail = 'Pentru cererea asta exista deja un credit.';
  end if;

  -- Nu se semneaza ce nu s-a trimis. Verificarea sta si aici, nu doar in
  -- serviciu: e chiar conditia care da inteles semnaturii.
  if v_cerere.contract_trimis_la is null or coalesce(btrim(v_cerere.contract_html), '') = '' then
    raise exception 'CONTRACT_LIPSA'
      using detail = 'Cererea nu are un contract trimis clientului; nu poate fi semnata.';
  end if;

  if coalesce(btrim(p_contract_url), '') = '' then
    raise exception 'CONTRACT_NESALVAT'
      using detail = 'Semnatura cere PDF-ul contractului deja urcat in storage.';
  end if;

  select * into v_cont from public.conturi_bancare c where c.id = p_id_cont for update;
  if not found then
    raise exception 'CONT_INEXISTENT' using detail = 'Contul de creditare nu exista.';
  end if;

  if v_cont.id_user <> v_cerere.id_user then
    raise exception 'CONT_STRAIN' using detail = 'Contul de creditare nu apartine solicitantului.';
  end if;

  -- Creditul se acorda in RON; un cont in alta valuta ar cere o conversie pe
  -- care produsul nu o prevede.
  if v_cont.valuta <> 'RON' then
    raise exception 'VALUTA_NESUPORTATA'
      using detail = format('Creditul se vireaza numai in conturi RON; contul ales e in %s.', v_cont.valuta);
  end if;

  -- Graficul vine din afara, deci se verifica: suma principalelor trebuie sa dea
  -- exact creditul, altfel soldul nu s-ar putea niciodata inchide pe zero.
  select coalesce(sum((elem->>'principal')::numeric), 0), count(*)
    into v_suma_grafic, v_numar_rate
    from jsonb_array_elements(p_grafic) elem;

  if v_numar_rate <> v_cerere.luni then
    raise exception 'GRAFIC_INVALID'
      using detail = format('Graficul are %s rate, cererea e pe %s luni.', v_numar_rate, v_cerere.luni);
  end if;

  if v_suma_grafic <> v_cerere.suma_ceruta then
    raise exception 'GRAFIC_INVALID'
      using detail = format('Suma principalelor din grafic (%s) nu da creditul acordat (%s).',
                            v_suma_grafic, v_cerere.suma_ceruta);
  end if;

  insert into public.credite (
    id_cerere, id_user, id_cont_creditare, principal, dobanda_anuala, luni,
    rata_lunara, dae, sold_ramas, semnatura, contract_url
  )
  select p_id_cerere, v_cerere.id_user, v_cont.id, v_cerere.suma_ceruta,
         pr.dobanda_anuala, v_cerere.luni, p_rata_lunara, p_dae, v_cerere.suma_ceruta,
         coalesce(p_semnatura, '{}'::jsonb), p_contract_url
    from public.credit_produse pr
   where pr.id = v_cerere.id_produs
  returning * into v_credit;

  insert into public.credit_rate (
    id_credit, numar_rata, scadenta, principal_rata, dobanda_rata, rata_totala, sold_dupa
  )
  select v_credit.id,
         (elem->>'numar')::integer,
         (elem->>'scadenta')::date,
         (elem->>'principal')::numeric,
         (elem->>'dobanda')::numeric,
         (elem->>'total')::numeric,
         (elem->>'sold_dupa')::numeric
    from jsonb_array_elements(p_grafic) elem;

  -- Banii vin de la banca, nu dintr-un alt cont: tranzactia are numai partea de
  -- incasare. `tranzactii_parti_check` cere exact atat — cel putin una din parti.
  update public.conturi_bancare
     set sold = sold + v_cerere.suma_ceruta
   where id = v_cont.id
  returning * into v_cont;

  insert into public.tranzactii (id_user_recieve, id_cont_recieve, suma, valuta, descriere)
  values (v_cerere.id_user, v_cont.id, v_cerere.suma_ceruta, 'RON',
          'Acordare credit ' || (select nume from public.credit_produse where id = v_cerere.id_produs))
  returning * into v_tranz;

  update public.credit_cereri set status = 'acceptata' where id = p_id_cerere;

  insert into public.credit_evenimente (id_cerere, id_credit, tip, actor, detalii)
  values (p_id_cerere, v_credit.id, 'credit_acordat', 'sistem',
          jsonb_build_object('suma', v_cerere.suma_ceruta, 'luni', v_cerere.luni,
                             'rata_lunara', p_rata_lunara, 'id_tranzactie', v_tranz.id,
                             'contract_url', p_contract_url));

  perform public.anunta_utilizator(v_cerere.id_user, 'credit_acordat',
    jsonb_build_object('id_credit', v_credit.id, 'suma', v_cerere.suma_ceruta));

  return jsonb_build_object(
    'id_credit', v_credit.id,
    'id_tranzactie', v_tranz.id,
    'principal', v_credit.principal,
    'rata_lunara', v_credit.rata_lunara,
    'luni', v_credit.luni,
    'contract_url', v_credit.contract_url,
    'sold_cont_nou', v_cont.sold,
    'prima_scadenta', (select min(scadenta) from public.credit_rate where id_credit = v_credit.id)
  );
end;
$$;

comment on function public.credit_acorda(uuid, uuid, numeric, numeric, jsonb, jsonb, text) is
  'Acorda creditul: contract, grafic, virament si audit, atomic. Refuza semnatura daca dosarul nu are contract trimis clientului si PDF-ul deja urcat.';

revoke execute on function public.credit_acorda(uuid, uuid, numeric, numeric, jsonb, jsonb, text) from public, anon, authenticated;

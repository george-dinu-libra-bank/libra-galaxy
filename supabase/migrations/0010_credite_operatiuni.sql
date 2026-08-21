-- =============================================================================
-- Libra — operatiunile pe credit: acordare, incasare de rate, rambursare
--
-- Trei functii, toate dupa tiparul lui public.core_banking: SECURITY DEFINER,
-- search_path gol, coduri de eroare in `raise exception`, jsonb la retur.
--
-- De ce exista, cand backendul are deja service_role si ar putea face update-uri
-- directe: fiecare dintre ele muta bani SI scrie istoric SI schimba stari, iar
-- lucrurile astea trebuie sa reuseasca sau sa esueze impreuna. Trei apeluri REST
-- separate din Python n-ar avea nicio tranzactie in jur — o pana la mijloc ar
-- lasa banii virati fara contract, sau rata marcata platita fara sa fi fost.
--
-- Ce NU e aici, deliberat: calculul graficului de amortizare. El traieste in
-- backend/app/credit/amortizare.py, testat cu 44 de teste, si se transmite
-- incoace ca jsonb. O a doua implementare in plpgsql ar fi exact coliziunea pe
-- care o interzice REGULI.md #2, cu agravanta ca cele doua ar diverge tacut la
-- rotunjiri. Functiile de aici verifica insa ce primesc: un grafic a carui suma
-- de principal nu da exact creditul e respins.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Acordarea: contract + grafic + banii in cont, intr-o singura tranzactie
-- -----------------------------------------------------------------------------
create or replace function public.credit_acorda(
  p_id_cerere   uuid,
  p_id_cont     uuid,
  p_rata_lunara numeric,
  p_dae         numeric,
  p_grafic      jsonb,
  p_semnatura   jsonb default '{}'::jsonb
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
    rata_lunara, dae, sold_ramas, semnatura
  )
  select p_id_cerere, v_cerere.id_user, v_cont.id, v_cerere.suma_ceruta,
         pr.dobanda_anuala, v_cerere.luni, p_rata_lunara, p_dae, v_cerere.suma_ceruta,
         coalesce(p_semnatura, '{}'::jsonb)
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
                             'rata_lunara', p_rata_lunara, 'id_tranzactie', v_tranz.id));

  perform public.anunta_utilizator(v_cerere.id_user, 'credit_acordat',
    jsonb_build_object('id_credit', v_credit.id, 'suma', v_cerere.suma_ceruta));

  return jsonb_build_object(
    'id_credit', v_credit.id,
    'id_tranzactie', v_tranz.id,
    'principal', v_credit.principal,
    'rata_lunara', v_credit.rata_lunara,
    'luni', v_credit.luni,
    'sold_cont_nou', v_cont.sold,
    'prima_scadenta', (select min(scadenta) from public.credit_rate where id_credit = v_credit.id)
  );
end;
$$;

comment on function public.credit_acorda(uuid, uuid, numeric, numeric, jsonb, jsonb) is
  'Acorda creditul: contract, grafic, virament si audit, atomic. Graficul se calculeaza in backend/app/credit/amortizare.py si se valideaza aici.';


-- -----------------------------------------------------------------------------
-- 2. Incasarea ratelor scadente
--
-- Idempotenta vine din `credit_rate_unica` plus filtrul pe status: o rata deja
-- platita nu mai e selectata, deci doua apeluri concurente nu o pot incasa de
-- doua ori. Lock-ul pe credit serializeaza apelurile pe acelasi credit.
-- -----------------------------------------------------------------------------
create or replace function public.credit_incaseaza_rate(
  p_id_credit uuid,
  p_pana_la   date default null
)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $$
declare
  v_este_srv  boolean := coalesce(auth.role(), 'service_role') = 'service_role';
  v_credit    public.credite%rowtype;
  v_cont      public.conturi_bancare%rowtype;
  v_rata      public.credit_rate%rowtype;
  v_tranz     public.tranzactii%rowtype;
  v_pana_la   date := coalesce(p_pana_la, current_date);
  v_platite   integer := 0;
  v_restante  integer := 0;
  v_total     numeric(14,2) := 0;
begin
  if not v_este_srv then
    raise exception 'NEAUTORIZAT' using detail = 'Incasarea ratelor se face numai din serviciul bancii.';
  end if;

  select * into v_credit from public.credite k where k.id = p_id_credit for update;
  if not found then
    raise exception 'CREDIT_INEXISTENT' using detail = 'Creditul nu exista.';
  end if;

  if v_credit.status in ('inchis', 'rambursat_anticipat') then
    return jsonb_build_object('rate_platite', 0, 'rate_restante', 0, 'total_incasat', 0,
                              'sold_ramas', v_credit.sold_ramas, 'status', v_credit.status);
  end if;

  select * into v_cont from public.conturi_bancare c where c.id = v_credit.id_cont_creditare for update;

  -- In ordinea scadentei: o rata mai veche se incaseaza inaintea uneia mai noi,
  -- iar cand banii se termina ne oprim acolo, nu sarim peste.
  --
  -- Se iau si ratele deja marcate 'restanta', nu doar cele 'programata': altfel
  -- o rata picata o data ar ramane picata pe veci, iar creditul n-ar mai putea
  -- fi adus la zi nici dupa ce omul alimenteaza contul.
  for v_rata in
    select * from public.credit_rate r
     where r.id_credit = p_id_credit and r.status in ('programata', 'restanta')
       and r.scadenta <= v_pana_la
     order by r.numar_rata
  loop
    if v_cont.sold < v_rata.rata_totala then
      update public.credit_rate set status = 'restanta' where id = v_rata.id;
      v_restante := v_restante + 1;

      insert into public.credit_evenimente (id_credit, tip, actor, detalii)
      values (p_id_credit, 'rata_restanta', 'sistem',
              jsonb_build_object('numar_rata', v_rata.numar_rata, 'suma', v_rata.rata_totala,
                                 'sold_cont', v_cont.sold));
      exit;
    end if;

    update public.conturi_bancare set sold = sold - v_rata.rata_totala
     where id = v_cont.id returning * into v_cont;

    insert into public.tranzactii (id_user_send, id_cont_send, suma, valuta, descriere)
    values (v_credit.id_user, v_cont.id, v_rata.rata_totala, 'RON',
            format('Rata %s/%s credit', v_rata.numar_rata, v_credit.luni))
    returning * into v_tranz;

    update public.credit_rate
       set status = 'platita', platita_la = now(), id_tranzactie = v_tranz.id
     where id = v_rata.id;

    update public.credite set sold_ramas = v_rata.sold_dupa
     where id = p_id_credit returning * into v_credit;

    v_platite := v_platite + 1;
    v_total := v_total + v_rata.rata_totala;
  end loop;

  -- Starea creditului, recitita din grafic ca sa nu depinda de ce s-a intamplat
  -- in bucla: daca nu mai exista nicio rata neplatita, creditul e inchis.
  if not exists (select 1 from public.credit_rate r
                  where r.id_credit = p_id_credit and r.status in ('programata', 'restanta')) then
    update public.credite set status = 'inchis', inchis_la = now(), sold_ramas = 0
     where id = p_id_credit returning * into v_credit;

    insert into public.credit_evenimente (id_credit, tip, actor, detalii)
    values (p_id_credit, 'credit_inchis', 'sistem', jsonb_build_object('motiv', 'toate ratele platite'));
  elsif exists (select 1 from public.credit_rate r where r.id_credit = p_id_credit and r.status = 'restanta') then
    update public.credite set status = 'restant' where id = p_id_credit returning * into v_credit;
  elsif v_credit.status = 'restant' then
    -- Restantele s-au stins, dar mai sunt rate viitoare: creditul redevine
    -- curent. Fara ramura asta ar ramane marcat 'restant' pana la final.
    update public.credite set status = 'activ' where id = p_id_credit returning * into v_credit;
  end if;

  if v_platite > 0 then
    perform public.anunta_utilizator(v_credit.id_user, 'rate_incasate',
      jsonb_build_object('id_credit', p_id_credit, 'rate', v_platite, 'total', v_total));
  end if;

  return jsonb_build_object(
    'rate_platite', v_platite,
    'rate_restante', v_restante,
    'total_incasat', v_total,
    'sold_ramas', v_credit.sold_ramas,
    'status', v_credit.status,
    'sold_cont', v_cont.sold
  );
end;
$$;

comment on function public.credit_incaseaza_rate(uuid, date) is
  'Incaseaza ratele scadente pana la o data. Idempotenta prin filtrul pe status si lock pe credit.';


-- -----------------------------------------------------------------------------
-- 3. Rambursarea anticipata, partiala sau integrala
--
-- `p_grafic_nou` gol inseamna stingere completa. Altfel, graficul ramas se
-- inlocuieste cu cel primit — recalculat tot in amortizare.py, pe soldul nou.
-- -----------------------------------------------------------------------------
create or replace function public.credit_ramburseaza_anticipat(
  p_id_credit         uuid,
  p_principal_platit  numeric,
  p_dobanda_acumulata numeric default 0,
  p_grafic_nou        jsonb default null
)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $$
declare
  v_este_srv boolean := coalesce(auth.role(), 'service_role') = 'service_role';
  v_credit   public.credite%rowtype;
  v_cont     public.conturi_bancare%rowtype;
  v_tranz    public.tranzactii%rowtype;
  v_total    numeric(14,2);
  v_integral boolean;
  v_suma_nou numeric(14,2);
begin
  if not v_este_srv then
    raise exception 'NEAUTORIZAT' using detail = 'Operatiunea se face numai din serviciul bancii.';
  end if;

  if p_principal_platit is null or p_principal_platit <= 0 then
    raise exception 'SUMA_INVALIDA' using detail = 'Suma rambursata trebuie sa fie mai mare decat 0.';
  end if;

  select * into v_credit from public.credite k where k.id = p_id_credit for update;
  if not found then
    raise exception 'CREDIT_INEXISTENT' using detail = 'Creditul nu exista.';
  end if;

  if v_credit.status in ('inchis', 'rambursat_anticipat') then
    raise exception 'CREDIT_INCHIS' using detail = 'Creditul e deja stins.';
  end if;

  if p_principal_platit > v_credit.sold_ramas then
    raise exception 'SUMA_PESTE_SOLD'
      using detail = format('Soldul e %s RON, s-a cerut rambursarea a %s RON.',
                            v_credit.sold_ramas, p_principal_platit);
  end if;

  v_integral := p_principal_platit = v_credit.sold_ramas;
  v_total := p_principal_platit + coalesce(p_dobanda_acumulata, 0);

  select * into v_cont from public.conturi_bancare c where c.id = v_credit.id_cont_creditare for update;

  if v_cont.sold < v_total then
    raise exception 'FONDURI_INSUFICIENTE'
      using detail = format('Sold disponibil: %s RON, necesar: %s RON.', v_cont.sold, v_total);
  end if;

  -- La rambursare partiala, graficul nou trebuie sa acopere exact soldul ramas.
  if not v_integral then
    if p_grafic_nou is null or jsonb_array_length(p_grafic_nou) = 0 then
      raise exception 'GRAFIC_LIPSA' using detail = 'Rambursarea partiala are nevoie de graficul recalculat.';
    end if;

    select coalesce(sum((elem->>'principal')::numeric), 0) into v_suma_nou
      from jsonb_array_elements(p_grafic_nou) elem;

    if v_suma_nou <> v_credit.sold_ramas - p_principal_platit then
      raise exception 'GRAFIC_INVALID'
        using detail = format('Graficul nou insumeaza %s, iar soldul dupa rambursare ar fi %s.',
                              v_suma_nou, v_credit.sold_ramas - p_principal_platit);
    end if;
  end if;

  update public.conturi_bancare set sold = sold - v_total
   where id = v_cont.id returning * into v_cont;

  insert into public.tranzactii (id_user_send, id_cont_send, suma, valuta, descriere)
  values (v_credit.id_user, v_cont.id, v_total, 'RON',
          case when v_integral then 'Rambursare anticipata integrala credit'
               else 'Rambursare anticipata partiala credit' end)
  returning * into v_tranz;

  -- Ratele viitoare dispar in ambele cazuri; la rambursare partiala sunt
  -- inlocuite imediat cu graficul recalculat.
  update public.credit_rate set status = 'anulata'
   where id_credit = p_id_credit and status in ('programata', 'restanta');

  if v_integral then
    update public.credite
       set sold_ramas = 0, status = 'rambursat_anticipat', inchis_la = now()
     where id = p_id_credit returning * into v_credit;
  else
    insert into public.credit_rate (
      id_credit, numar_rata, scadenta, principal_rata, dobanda_rata, rata_totala, sold_dupa
    )
    select p_id_credit,
           (elem->>'numar')::integer,
           (elem->>'scadenta')::date,
           (elem->>'principal')::numeric,
           (elem->>'dobanda')::numeric,
           (elem->>'total')::numeric,
           (elem->>'sold_dupa')::numeric
      from jsonb_array_elements(p_grafic_nou) elem;

    update public.credite
       set sold_ramas = v_credit.sold_ramas - p_principal_platit,
           rata_lunara = (p_grafic_nou->0->>'total')::numeric,
           status = 'activ'
     where id = p_id_credit returning * into v_credit;
  end if;

  insert into public.credit_evenimente (id_credit, tip, actor, detalii)
  values (p_id_credit,
          case when v_integral then 'rambursare_integrala' else 'rambursare_partiala' end,
          'client',
          jsonb_build_object('principal', p_principal_platit, 'dobanda', p_dobanda_acumulata,
                             'total', v_total, 'id_tranzactie', v_tranz.id));

  perform public.anunta_utilizator(v_credit.id_user, 'rambursare_anticipata',
    jsonb_build_object('id_credit', p_id_credit, 'total', v_total, 'integral', v_integral));

  return jsonb_build_object(
    'id_tranzactie', v_tranz.id,
    'principal_platit', p_principal_platit,
    'dobanda_platita', coalesce(p_dobanda_acumulata, 0),
    'total_platit', v_total,
    'sold_ramas', v_credit.sold_ramas,
    'status', v_credit.status,
    'sold_cont', v_cont.sold
  );
end;
$$;

comment on function public.credit_ramburseaza_anticipat(uuid, numeric, numeric, jsonb) is
  'Rambursare anticipata. Fara grafic nou = stingere integrala; cu grafic = partiala, cu recalculare.';


-- -----------------------------------------------------------------------------
-- 4. Niciuna nu e apelabila din client
--
-- Toate trei muta bani si schimba stari de contract. Backendul le apeleaza cu
-- service_role, care oricum ocoleste grantul; expunerea prin /rest/v1/rpc/* ar
-- fi doar suprafata de atac in plus (vezi regula 0028/0029 din database linter).
-- -----------------------------------------------------------------------------
revoke execute on function public.credit_acorda(uuid, uuid, numeric, numeric, jsonb, jsonb) from public, anon, authenticated;
revoke execute on function public.credit_incaseaza_rate(uuid, date) from public, anon, authenticated;
revoke execute on function public.credit_ramburseaza_anticipat(uuid, numeric, numeric, jsonb) from public, anon, authenticated;

grant execute on function public.credit_acorda(uuid, uuid, numeric, numeric, jsonb, jsonb) to service_role;
grant execute on function public.credit_incaseaza_rate(uuid, date) to service_role;
grant execute on function public.credit_ramburseaza_anticipat(uuid, numeric, numeric, jsonb) to service_role;

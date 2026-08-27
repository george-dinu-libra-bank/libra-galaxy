-- =============================================================================
-- 0047 — Poprirea: se indisponibilizeaza o SUMA, nu tot contul
--
-- 0030 a dat bancii un intrerupator: `blocat_administrativ`, pornit sau oprit,
-- si din contul blocat nu mai iese niciun ban. E unealta potrivita pentru
-- frauda, unde nu stii inca nici ce, nici cat.
--
-- Poprirea e alta operatiune. Un executor judecatoresc sau ANAF cere o suma
-- anume; restul banilor raman ai omului si trebuie sa poata fi folositi. Cu
-- unealta de azi analistul avea doar doua variante, amandoua gresite: blocheaza
-- tot (pedepseste clientul peste ce s-a cerut) sau nu face nimic.
--
-- TREI DECIZII, cu motivele lor:
--
-- 1. Poprirea sta pe CLIENT, nu pe cont. Un rand per dosar de executare,
--    oricate conturi are omul. Pusa pe un singur cont, ar fi fost decorativa:
--    clientul isi muta banii in contul vecin si trece pe langa ea.
--
-- 2. Bariera e un trigger pe `conturi_bancare`, ca in 0030 si din acelasi
--    motiv: prinde ORICE drum prin care scade soldul — `core_banking`,
--    `core_banking_groups`, plata cu cardul (0035), schimbul valutar (0019),
--    operatiunile de credit (0010), si orice s-ar adauga maine — fara sa
--    rescriu corpul unor functii mari si delicate.
--
-- 3. SUMA INDISPONIBILA E `min(disponibil, rest_de_plata)`, nu restul de plata.
--    Asta e partea in care e usor sa gresesti. Prima varianta a acestei
--    migratii spunea „soldul cumulat nu poate scadea sub restul de plata" — o
--    regula care se rupe exact in cazul obisnuit: poprire de 5000 pe un om care
--    are 300. Soldul lui e DEJA sub restul de plata, deci regula ar fi refuzat
--    orice iesire, inclusiv virarea bancii catre creditor. Formularea corecta e
--    „nu poti cheltui bani popriti": cine are mai putin decat suma poprita are
--    tot ce are indisponibil.
--
-- Ce NU face migratia asta, deliberat: veniturile neurmaribile (cota de 1/3 din
-- salariu, pensiile sub plafon), ordinea de prioritate intre mai multi
-- creditori, expirarea automata. Sunt decizii juridice, nu tehnice.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Dosarul
-- -----------------------------------------------------------------------------

create table if not exists public.popriri (
  id             uuid primary key default gen_random_uuid(),
  id_utilizator  uuid not null references public.profiles (id) on delete cascade,

  -- Cine cere banii si in ce dosar. Ajung amandoua in notificarea catre client:
  -- un om caruia i s-au blocat banii are dreptul sa stie de la cine sa ceara
  -- lamuriri, fara sa sune banca.
  creditor       text not null,
  dosar          text,

  suma_totala    numeric(14,2) not null check (suma_totala > 0),
  suma_incasata  numeric(14,2) not null default 0 check (suma_incasata >= 0),

  -- Doar RON deocamdata. Conturile in alta valuta intra oricum in calcul, prin
  -- `converteste`; valuta de aici e cea a dosarului de executare.
  valuta         text not null default 'RON',

  status         text not null default 'activa'
                 check (status in ('activa', 'stinsa', 'ridicata')),

  creat_la       timestamptz not null default now(),
  incheiat_la    timestamptz,
  id_admin       uuid references public.profiles (id) on delete set null,
  observatie     text,

  constraint popriri_incasat_sub_total check (suma_incasata <= suma_totala)
);

comment on table public.popriri is
  'Popriri instituite pe conturile unui client. Indisponibilizeaza o suma pe '
  'toate conturile lui, nu contul intreg (aceea e blocarea din 0030).';
comment on column public.popriri.suma_incasata is
  'Cat s-a virat deja catre creditor. Restul de plata = suma_totala - suma_incasata.';
comment on column public.popriri.status is
  'activa = indisponibilizeaza; stinsa = suma s-a adunat; ridicata = anulata de banca.';

-- Trigger-ul intreaba la FIECARE scadere de sold daca omul are vreo poprire
-- activa. Indexul partial face din intrebarea aia o singura proba de index
-- pentru clientul obisnuit, care n-are niciuna.
create index if not exists popriri_active_idx
  on public.popriri (id_utilizator)
  where status = 'activa';

create index if not exists popriri_coada_idx
  on public.popriri (status, creat_la desc);


alter table public.popriri enable row level security;

-- Clientul isi vede popririle — trebuie sa poata afla de ce nu-si poate misca
-- banii. Nu le poate scrie: nu exista politica de insert sau update pentru
-- `authenticated`, ca la `conturi_bancare`. Se instituie doar prin RPC-urile de
-- mai jos, chemate cu service_role de backend, dupa verificarea de rol.
drop policy if exists "popriri: select" on public.popriri;
create policy "popriri: select"
  on public.popriri for select to authenticated
  using (auth.uid() = id_utilizator or public.este_administrator());


-- -----------------------------------------------------------------------------
-- 2. Cat e indisponibil, intr-un singur loc
--
-- Aceleasi doua marimi sunt cerute din trei parti: trigger-ul (ca sa refuze),
-- RPC-ul de incasare (ca sa stie cat poate lua) si interfata (ca sa arate
-- omului). Scrise de trei ori, ar fi deviat una de alta.
-- -----------------------------------------------------------------------------

create or replace function public.poprire_rest_de_plata(p_id_utilizator uuid)
returns numeric
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(sum(p.suma_totala - p.suma_incasata), 0)
  from public.popriri p
  where p.id_utilizator = p_id_utilizator
    and p.status = 'activa';
$$;

comment on function public.poprire_rest_de_plata(uuid) is
  'Cat mai are de virat clientul, in RON, peste toate popririle active.';

-- NU si pentru `authenticated`. E `security definer` si primeste id-ul ca
-- parametru, deci un client autentificat ar fi putut intreba cat are de plata
-- ORICINE altcineva. Interfata nu are nevoie de ea: clientul isi citeste
-- popririle direct din tabela, unde politica de select ii da doar randurile lui.
revoke all on function public.poprire_rest_de_plata(uuid) from public, anon, authenticated;
grant execute on function public.poprire_rest_de_plata(uuid) to service_role;


-- Soldul cumulat al conturilor deschise, in RON. Conturile inchise (0040) nu
-- intra: nu mai pot da bani.
create or replace function public.poprire_disponibil_total(
  p_id_utilizator  uuid,
  p_id_cont_exclus uuid default null
)
returns numeric
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(sum(public.converteste(c.sold, c.valuta, 'RON')), 0)
  from public.conturi_bancare c
  where c.id_user = p_id_utilizator
    and c.inchis_la is null
    and (p_id_cont_exclus is null or c.id <> p_id_cont_exclus);
$$;

comment on function public.poprire_disponibil_total(uuid, uuid) is
  'Soldul cumulat al conturilor deschise, in RON. `p_id_cont_exclus` sare peste '
  'un cont — folosit de trigger, care are randul lui in `new`, nu in tabela.';

revoke all on function public.poprire_disponibil_total(uuid, uuid) from public, anon, authenticated;
grant execute on function public.poprire_disponibil_total(uuid, uuid) to service_role;


-- -----------------------------------------------------------------------------
-- 3. Bariera
--
-- Banii pot INTRA intr-un cont poprit (un salariu, o rambursare) — se adauga la
-- ce e indisponibil, si de acolo ii ia banca. Nu pot IESI decat peste suma
-- poprita.
-- -----------------------------------------------------------------------------

create or replace function public.conturi_opreste_iesirile_daca_poprit()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_ramas        numeric(14,2);
  v_alte_conturi numeric(14,2);
  v_inainte      numeric(14,2);
  v_dupa         numeric(14,2);
  v_indisponibil numeric(14,2);
begin
  -- Intrarile trec mereu, fara nicio interogare.
  if new.sold >= old.sold then
    return new;
  end if;

  -- Virarea catre creditor scade ea insasi soldul, si trebuie sa poata cobori
  -- SUB suma indisponibila — altfel poprirea n-ar putea fi platita niciodata
  -- din banii pe care tot ea ii tine blocati. Steagul e pus de
  -- `incaseaza_poprirea` cu `set_config(..., is_local => true)`, deci moare la
  -- sfarsitul tranzactiei. Nu poate fi pus de un client: singura functie care
  -- il pune e revocata pentru toti in afara de service_role.
  if coalesce(current_setting('app.incasare_poprire', true), '') = 'on' then
    return new;
  end if;

  -- Ieftin pentru cei fara popriri: o proba pe indexul partial.
  if not exists (
    select 1 from public.popriri p
    where p.id_utilizator = old.id_user and p.status = 'activa'
  ) then
    return new;
  end if;

  v_ramas := public.poprire_rest_de_plata(old.id_user);

  if v_ramas <= 0 then
    return new;
  end if;

  -- Randul care se modifica nu e inca in tabela cu valoarea noua, deci se scoate
  -- din suma si se adauga inapoi de doua ori: o data cu vechea valoare, o data
  -- cu cea noua.
  v_alte_conturi := public.poprire_disponibil_total(old.id_user, old.id);
  v_inainte      := v_alte_conturi + public.converteste(old.sold, old.valuta, 'RON');
  v_dupa         := v_alte_conturi + public.converteste(new.sold, new.valuta, 'RON');

  -- Vezi decizia 3 din antet: cine are mai putin decat suma poprita are tot ce
  -- are indisponibil. `least` e toata diferenta dintre o poprire care merge si
  -- una care blocheaza si banca.
  v_indisponibil := least(v_inainte, v_ramas);

  if v_dupa < v_indisponibil then
    raise exception 'POPRIRE_ACTIVA'
      using detail = 'O poprire tine indisponibila suma de ' ||
                     trim(to_char(v_indisponibil, 'FM999999999990.00')) ||
                     ' RON din conturile acestui client.';
  end if;

  return new;
end;
$$;

comment on function public.conturi_opreste_iesirile_daca_poprit() is
  'Refuza iesirile care ar cobori soldul cumulat sub suma poprita. Intrarile trec.';

-- Fara asta, `get_advisors` o raporteaza (pe drept) ca functie SECURITY DEFINER
-- chemabila prin `/rest/v1/rpc/...` de oricine. Nu poate face rau chemata de-a
-- dreptul — o functie de trigger fara context de trigger crapa — dar nu are ce
-- cauta in API. Postgres verifica dreptul de EXECUTE la CREAREA trigger-ului,
-- nu la fiecare declansare, deci revocarea nu opreste bariera.
--
-- Aceeasi observatie e valabila si pentru `conturi_opreste_iesirile_daca_blocat`
-- din 0030, care e raportata la fel. NU o ating aici: e alta migratie si alta
-- decizie, si o semnalez in loc sa o schimb tacit.
revoke all on function public.conturi_opreste_iesirile_daca_poprit()
  from public, anon, authenticated;

drop trigger if exists conturi_before_update_poprire on public.conturi_bancare;

-- Numele conteaza: Postgres ruleaza trigger-ele BEFORE in ordinea alfabetica a
-- numelui, si `...blocare` vine inaintea lui `...poprire`. Un cont blocat
-- administrativ e refuzat cu CONT_BLOCAT, motivul lui adevarat, nu cu
-- POPRIRE_ACTIVA — analistul citeste ce s-a intamplat, nu ce s-a nimerit.
create trigger conturi_before_update_poprire
  before update on public.conturi_bancare
  for each row execute function public.conturi_opreste_iesirile_daca_poprit();


-- -----------------------------------------------------------------------------
-- 4. Instituirea
--
-- Clientul e anuntat imediat, cu creditorul si dosarul in text. `tip` e
-- 'blocare' fiindca aia e valoarea pe care o cunoaste baza — vezi 0042, unde
-- un 'succes' inventat a dat rollback la operatiuni intregi. Vocabularul e
-- inchis si in `frontend/src/lib/data/notificari.ts`.
-- -----------------------------------------------------------------------------

create or replace function public.instituie_poprire(
  p_id_utilizator uuid,
  p_creditor      text,
  p_suma          numeric,
  p_id_admin      uuid,
  p_dosar         text default null,
  p_observatie    text default null
)
returns public.popriri
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_poprire public.popriri%rowtype;
  v_mesaj   text;
begin
  if p_id_utilizator is null then
    raise exception 'CLIENT_INEXISTENT' using detail = 'Poprirea cere un client.';
  end if;

  if coalesce(trim(p_creditor), '') = '' then
    raise exception 'FARA_CREDITOR'
      using detail = 'Poprirea trebuie sa spuna cine cere banii.';
  end if;

  if p_suma is null or p_suma <= 0 then
    raise exception 'SUMA_INVALIDA' using detail = 'Suma poprita trebuie sa fie pozitiva.';
  end if;

  if not exists (select 1 from public.profiles p where p.id = p_id_utilizator) then
    raise exception 'CLIENT_INEXISTENT' using detail = 'Clientul nu exista.';
  end if;

  insert into public.popriri (
    id_utilizator, creditor, dosar, suma_totala, id_admin, observatie
  )
  values (
    p_id_utilizator, trim(p_creditor), nullif(trim(p_dosar), ''),
    round(p_suma, 2), p_id_admin, nullif(trim(p_observatie), '')
  )
  returning * into v_poprire;

  v_mesaj := 'Am primit o poprire de la ' || v_poprire.creditor ||
             case when v_poprire.dosar is null then ''
                  else ' (dosar ' || v_poprire.dosar || ')' end ||
             '. Suma de ' || trim(to_char(v_poprire.suma_totala, 'FM999999999990.00')) ||
             ' RON este indisponibila in conturile tale pana la stingerea ei. ' ||
             'Banii care depasesc suma poprita raman la dispozitia ta, iar incasarile ' ||
             'intra normal. Pentru contestatii te adresezi creditorului.';

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (v_poprire.id_utilizator, 'Poprire pe conturi', v_mesaj, 'blocare');

  perform public.anunta_utilizator(
    v_poprire.id_utilizator, 'notificare',
    jsonb_build_object('id_poprire', v_poprire.id, 'status', 'activa')
  );

  return v_poprire;
end;
$$;

comment on function public.instituie_poprire(uuid, text, numeric, uuid, text, text) is
  'Instituie o poprire pe conturile unui client si il anunta.';

revoke all on function public.instituie_poprire(uuid, text, numeric, uuid, text, text)
  from public, anon, authenticated;
grant execute on function public.instituie_poprire(uuid, text, numeric, uuid, text, text)
  to service_role;


-- -----------------------------------------------------------------------------
-- 5. Incasarea — virarea catre creditor
--
-- Fara suma, ia cat se poate acum: `min(disponibil, rest_de_plata)`. Asta e
-- forma folosita in practica, fiindca banii pica in transe.
--
-- Conturile blocate administrativ (0030) sunt SARITE, nu tratate ca eroare.
-- Trigger-ul din 0030 le-ar refuza oricum, si o poprire nu trebuie sa cada in
-- intregime fiindca omul are, pe langa, si un cont inghetat pentru frauda.
--
-- Totul intr-o singura tranzactie: ori se debiteaza toate conturile SI creste
-- `suma_incasata` SI se scrie istoricul, ori nu se intampla nimic.
-- -----------------------------------------------------------------------------

create or replace function public.incaseaza_poprirea(
  p_id_poprire uuid,
  p_id_admin   uuid,
  p_suma       numeric default null
)
returns public.popriri
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_poprire     public.popriri%rowtype;
  v_ramas       numeric(14,2);
  v_disponibil  numeric(14,2);
  -- Cat s-a hotarat sa se ia (`v_tinta`) si cat a mai ramas de luat pe masura
  -- ce se golesc conturile (`v_de_incasat`). Diferenta lor e cat s-a luat
  -- efectiv — poate fi mai putin, daca rotunjirile de curs lasa banuti in urma.
  v_tinta       numeric(14,2);
  v_de_incasat  numeric(14,2);
  v_incasat     numeric(14,2);
  v_cont        public.conturi_bancare%rowtype;
  v_in_ron      numeric(14,2);
  v_in_cont     numeric(14,2);
  v_mesaj       text;
begin
  select p.* into v_poprire
  from public.popriri p
  where p.id = p_id_poprire
  for update;

  if not found then
    raise exception 'POPRIRE_INEXISTENTA' using detail = 'Poprirea nu exista.';
  end if;

  if v_poprire.status <> 'activa' then
    raise exception 'POPRIRE_INCHEIATA'
      using detail = 'Poprirea a fost deja ' || v_poprire.status || '.';
  end if;

  v_ramas      := v_poprire.suma_totala - v_poprire.suma_incasata;
  v_disponibil := public.poprire_disponibil_total(v_poprire.id_utilizator, null);
  v_tinta      := least(coalesce(round(p_suma, 2), v_ramas), v_ramas, v_disponibil);
  v_de_incasat := v_tinta;

  if p_suma is not null and round(p_suma, 2) > v_ramas then
    raise exception 'PESTE_RESTUL_DE_PLATA'
      using detail = 'Poprirea mai are de incasat doar ' ||
                     trim(to_char(v_ramas, 'FM999999999990.00')) || ' RON.';
  end if;

  if v_tinta <= 0 then
    raise exception 'FONDURI_INSUFICIENTE'
      using detail = 'Clientul nu are bani in conturi pentru aceasta poprire.';
  end if;

  -- Vezi trigger-ul: virarea trebuie sa poata cobori sub suma indisponibila,
  -- fiindca exact aceia sunt banii popriti.
  --
  -- Steagul se stinge imediat dupa bucla, si asta NU e o precautie teoretica:
  -- `is_local => true` inseamna „pana la capatul TRANZACTIEI", nu „pana la
  -- capatul functiei". Prins la testul cap-coada — doua operatiuni in aceeasi
  -- tranzactie, iar a doua trecea pe langa poprire fiindca prima lasase steagul
  -- ridicat. Prin PostgREST fiecare RPC are tranzactia lui, deci gaura nu se
  -- vedea azi; s-ar fi vazut in prima functie care incaseaza si mai face ceva.
  perform set_config('app.incasare_poprire', 'on', true);

  -- Cel mai vechi cont primul, ca la consolidare (0037): o ordine stabila, pe
  -- care clientul o vede la fel in extras de fiecare data.
  for v_cont in
    select c.* from public.conturi_bancare c
    where c.id_user = v_poprire.id_utilizator
      and c.inchis_la is null
      and c.sold > 0
      and not c.blocat_administrativ
    order by c.creat_la
    for update
  loop
    exit when v_de_incasat <= 0;

    v_in_ron  := least(public.converteste(v_cont.sold, v_cont.valuta, 'RON'), v_de_incasat);
    v_in_cont := public.converteste(v_in_ron, 'RON', v_cont.valuta);

    -- Rotunjirile celor doua conversii pot cere cu un ban mai mult decat are
    -- contul. Se ia cat e, nu se scrie sold negativ.
    v_in_cont := least(v_in_cont, v_cont.sold);

    if v_in_cont <= 0 then
      continue;
    end if;

    update public.conturi_bancare c
       set sold = c.sold - v_in_cont, modificat_la = now()
     where c.id = v_cont.id;

    -- O iesire cu un singur capat: creditorul n-are cont la noi. Acelasi tipar
    -- ca plata cu cardul catre un comerciant din afara bancii, si trigger-ul
    -- `tranzactii_cere_o_parte` (0034) cere fix o parte.
    insert into public.tranzactii (
      id_user_send, id_cont_send, suma, valuta, descriere
    )
    values (
      v_poprire.id_utilizator, v_cont.id, v_in_cont, v_cont.valuta,
      'Poprire — virat catre ' || v_poprire.creditor
    );

    v_de_incasat := v_de_incasat - v_in_ron;
  end loop;

  -- Gata cu debitarea; poprirea redevine opozabila si bancii. La exceptie nu mai
  -- conteaza: tranzactia se da inapoi cu totul, steag cu tot.
  perform set_config('app.incasare_poprire', 'off', true);

  v_incasat := v_tinta - v_de_incasat;

  if v_incasat <= 0 then
    raise exception 'FONDURI_INSUFICIENTE'
      using detail = 'Nu s-a putut lua nimic din conturile clientului.';
  end if;

  update public.popriri p
     set suma_incasata = p.suma_incasata + v_incasat,
         id_admin      = p_id_admin,
         status        = case when p.suma_incasata + v_incasat >= p.suma_totala
                              then 'stinsa' else p.status end,
         incheiat_la   = case when p.suma_incasata + v_incasat >= p.suma_totala
                              then now() else p.incheiat_la end
   where p.id = p_id_poprire
  returning * into v_poprire;

  if v_poprire.status = 'stinsa' then
    v_mesaj := 'Poprirea de la ' || v_poprire.creditor ||
               ' a fost stinsa. Suma de ' ||
               trim(to_char(v_poprire.suma_totala, 'FM999999999990.00')) ||
               ' RON a fost virata integral, iar conturile tale functioneaza normal.';

    insert into public.notificari (id_utilizator, titlu, mesaj, tip)
    values (v_poprire.id_utilizator, 'Poprirea a fost stinsa', v_mesaj, 'deblocare');
  else
    v_mesaj := 'Am virat catre ' || v_poprire.creditor || ' suma de ' ||
               trim(to_char(v_poprire.suma_incasata, 'FM999999999990.00')) ||
               ' RON din poprire. Mai sunt de acoperit ' ||
               trim(to_char(v_poprire.suma_totala - v_poprire.suma_incasata,
                            'FM999999999990.00')) || ' RON.';

    insert into public.notificari (id_utilizator, titlu, mesaj, tip)
    values (v_poprire.id_utilizator, 'Plata partiala din poprire', v_mesaj, 'blocare');
  end if;

  perform public.anunta_utilizator(
    v_poprire.id_utilizator, 'notificare',
    jsonb_build_object('id_poprire', v_poprire.id, 'status', v_poprire.status)
  );

  return v_poprire;
end;
$$;

comment on function public.incaseaza_poprirea(uuid, uuid, numeric) is
  'Vireaza catre creditor din conturile clientului. Fara suma, ia cat se poate '
  'acum. Se stinge singura cand s-a adunat tot.';

revoke all on function public.incaseaza_poprirea(uuid, uuid, numeric)
  from public, anon, authenticated;
grant execute on function public.incaseaza_poprirea(uuid, uuid, numeric) to service_role;


-- -----------------------------------------------------------------------------
-- 6. Ridicarea
--
-- Poprirea gresita, contestata cu succes, sau retrasa de creditor. Banii deja
-- virati NU se intorc automat — au plecat catre creditor si nu mai sunt ai
-- bancii; se scrie asta in notificare, ca omul sa nu-i astepte degeaba. Acelasi
-- rationament ca la `redeschide_cont` (0040).
-- -----------------------------------------------------------------------------

create or replace function public.ridica_poprirea(
  p_id_poprire uuid,
  p_id_admin   uuid,
  p_motiv      text default null
)
returns public.popriri
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_poprire public.popriri%rowtype;
  v_mesaj   text;
begin
  select p.* into v_poprire
  from public.popriri p
  where p.id = p_id_poprire
  for update;

  if not found then
    raise exception 'POPRIRE_INEXISTENTA' using detail = 'Poprirea nu exista.';
  end if;

  if v_poprire.status <> 'activa' then
    raise exception 'POPRIRE_INCHEIATA'
      using detail = 'Poprirea a fost deja ' || v_poprire.status || '.';
  end if;

  update public.popriri p
     set status = 'ridicata', incheiat_la = now(), id_admin = p_id_admin,
         observatie = coalesce(nullif(trim(p_motiv), ''), p.observatie)
   where p.id = p_id_poprire
  returning * into v_poprire;

  v_mesaj := coalesce(nullif(trim(p_motiv), ''),
                      'Poprirea de la ' || v_poprire.creditor || ' a fost ridicata.') ||
             ' Banii din conturile tale sunt din nou disponibili.' ||
             case when v_poprire.suma_incasata > 0
                  then ' Sumele deja virate catre creditor nu se intorc automat — ' ||
                       'pentru ele te adresezi creditorului.'
                  else '' end;

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (v_poprire.id_utilizator, 'Poprirea a fost ridicata', v_mesaj, 'deblocare');

  perform public.anunta_utilizator(
    v_poprire.id_utilizator, 'notificare',
    jsonb_build_object('id_poprire', v_poprire.id, 'status', 'ridicata')
  );

  return v_poprire;
end;
$$;

revoke all on function public.ridica_poprirea(uuid, uuid, text)
  from public, anon, authenticated;
grant execute on function public.ridica_poprirea(uuid, uuid, text) to service_role;

-- =============================================================================
-- 0040 — Inchiderea unui CONT BANCAR (nu a relatiei cu banca)
--
-- 0036-0038 acopera plecarea clientului de tot. Asta e alta operatiune, si se
-- confunda usor cu prima tocmai fiindca in romana "cont" inseamna amandoua:
-- aici se inchide un singur cont bancar, iar omul ramane client.
--
-- INCHIS, NU STERS. `conturi_bancare.inchis_la` in loc de `delete`, din doua
-- motive practice:
--
--   1. Istoricul isi pastreaza numele. `tranzactii.id_cont_send/recieve` sunt
--      ON DELETE SET NULL de la 0034 — la o stergere reala, o plata veche ar
--      arata "Cont sters" in loc de "Vacanta". Extrasul unui om nu trebuie sa
--      piarda informatie fiindca a inchis un cont acum doi ani.
--   2. Se poate da inapoi. O inchidere gresita se repara cu `redeschide_cont`;
--      un `delete` nu se repara deloc.
--
-- CONTUL PRINCIPAL NU SE POATE INCHIDE. E cel din `profiles.iban_cont`: il da
-- clientul mai departe ca IBAN, si e tinta consolidarii din 0037. Cine vrea sa
-- plece de tot inchide relatia (0036), nu contul principal.
--
-- Cardurile legate se inchid odata cu contul. `carduri.id_cont` e ON DELETE
-- RESTRICT (0027), deci nu se putea altfel oricum — dar si daca s-ar putea, un
-- card fara cont in spate nu mai are ce sa faca.
--
-- Soldul NU blocheaza cererea, se muta. Blocheaza doar: contul principal,
-- contul blocat administrativ, soldul negativ, si lipsa unui cont destinatie.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Marcajul de inchidere
-- -----------------------------------------------------------------------------

alter table public.conturi_bancare
  add column if not exists inchis_la timestamptz;

comment on column public.conturi_bancare.inchis_la is
  'Cand a fost inchis contul. NULL = deschis. Randul ramane, ca istoricul sa '
  'pastreze numele contului (tranzactii.id_cont_* sunt ON DELETE SET NULL).';

alter table public.carduri
  add column if not exists inchis_la timestamptz;

comment on column public.carduri.inchis_la is
  'Cardurile se inchid odata cu contul lor. NULL = activ.';

-- Listele cer mereu doar conturile deschise; indexul partial le serveste direct.
create index if not exists conturi_bancare_deschise_idx
  on public.conturi_bancare (id_user)
  where inchis_la is null;


-- -----------------------------------------------------------------------------
-- 2. Mutarea banilor intre doua conturi ale aceluiasi om — UN SINGUR LOC
--
-- Pana acum logica asta traia doar in `consolideaza_conturile` (0037). Acum e
-- nevoie de ea si la inchiderea unui cont, cu alta destinatie, si copierea ei ar
-- fi insemnat doua locuri in care se convertesc valute si se scrie in istoric.
-- Se extrage aici, si 0037 e rescris mai jos ca sa o foloseasca — ca sa nu ramana
-- doua variante care pot devia una de alta.
--
-- Contract: apelantul a blocat DEJA ambele randuri cu `for update`. Functia nu
-- ia lock-uri singura, tocmai ca apelantul sa poata decide ordinea si sa evite
-- deadlock-urile (consolidarea blocheaza intai destinatia, apoi sursele, in
-- ordinea `creat_la`).
-- -----------------------------------------------------------------------------

create or replace function public.muta_sold_intre_conturi(
  p_sursa       public.conturi_bancare,
  p_destinatie  public.conturi_bancare,
  p_descriere   text
)
returns numeric
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_suma numeric(14,2);
begin
  if p_sursa.sold <= 0 then
    return 0;
  end if;

  -- Valutele pot diferi: conversia trece prin aceeasi functie ca restul
  -- aplicatiei. Daca lipseste cursul, `converteste` ridica exceptie si se
  -- opreste tot — mai bine nicio mutare decat una la un curs inventat.
  v_suma := public.converteste(p_sursa.sold, p_sursa.valuta, p_destinatie.valuta);

  update public.conturi_bancare c
     set sold = 0, modificat_la = now()
   where c.id = p_sursa.id;

  update public.conturi_bancare c
     set sold = c.sold + v_suma, modificat_la = now()
   where c.id = p_destinatie.id;

  -- Se scrie in istoric ca orice alta miscare de bani. Acelasi om pe ambele
  -- capete: e o mutare intre conturile lui, nu o plata.
  insert into public.tranzactii (
    id_user_send, id_cont_send, id_user_recieve, id_cont_recieve,
    suma, valuta, descriere
  )
  values (
    p_sursa.id_user, p_sursa.id, p_destinatie.id_user, p_destinatie.id,
    v_suma, p_destinatie.valuta, p_descriere
  );

  return v_suma;
end;
$$;

comment on function public.muta_sold_intre_conturi(public.conturi_bancare, public.conturi_bancare, text) is
  'Muta tot soldul dintr-un cont in altul al aceluiasi om, cu conversie la '
  'cursul BNR si scriere in istoric. Apelantul blocheaza randurile inainte.';

revoke all on function public.muta_sold_intre_conturi(public.conturi_bancare, public.conturi_bancare, text)
  from public, anon, authenticated;


-- Consolidarea din 0037, rescrisa peste helper-ul de mai sus. Comportament
-- identic (aceeasi semnatura, acelasi rezultat, aceeasi ordine de blocare) —
-- doar ca partea care misca banii nu mai e duplicata.
create or replace function public.consolideaza_conturile(p_id_user uuid)
returns TABLE (id_cont uuid, nume text, suma numeric, valuta text)
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_principal public.conturi_bancare%rowtype;
  v_iban_cont text;
  v_sursa     public.conturi_bancare%rowtype;
  v_mutat     numeric(14,2);
begin
  if p_id_user is null then
    raise exception 'NEAUTENTIFICAT' using detail = 'Consolidarea cere un utilizator.';
  end if;

  select p.iban_cont into v_iban_cont from public.profiles p where p.id = p_id_user;

  if v_iban_cont is null then
    raise exception 'FARA_CONT_PRINCIPAL'
      using detail = 'Profilul nu are un IBAN de cont principal.';
  end if;

  select c.* into v_principal
  from public.conturi_bancare c
  where c.id_user = p_id_user and c.iban = v_iban_cont
  for update;

  if not found then
    raise exception 'FARA_CONT_PRINCIPAL'
      using detail = 'Contul principal al clientului nu mai exista.';
  end if;

  if v_principal.blocat_administrativ then
    raise exception 'CONT_BLOCAT'
      using detail = 'Contul principal e blocat; deblocheaza-l inainte de consolidare.';
  end if;

  for v_sursa in
    select c.* from public.conturi_bancare c
    where c.id_user = p_id_user
      and c.id <> v_principal.id
      and c.sold > 0
      -- Un cont deja inchis (0040) si-a mutat soldul la inchidere; nu mai are ce
      -- da, si nu trebuie sa reapara in raportul de consolidare.
      and c.inchis_la is null
    order by c.creat_la
    for update
  loop
    v_mutat := public.muta_sold_intre_conturi(
      v_sursa, v_principal, 'Consolidare inainte de inchiderea contului'
    );

    id_cont := v_sursa.id;
    nume    := v_sursa.nume;
    suma    := v_mutat;
    valuta  := v_principal.valuta;
    return next;
  end loop;

  return;
end;
$$;

revoke all on function public.consolideaza_conturile(uuid) from public, anon, authenticated;
grant execute on function public.consolideaza_conturile(uuid) to service_role;


-- -----------------------------------------------------------------------------
-- 3. Cererea clientului
--
-- Acelasi tipar ca `cereri_stergere_cont` (0036), cu o singura diferenta de
-- fond: unicitatea cererii deschise e PER CONT, nu per om. Cineva cu trei
-- conturi trebuie sa poata cere inchiderea a doua dintre ele deodata.
-- -----------------------------------------------------------------------------

create table if not exists public.cereri_inchidere_cont (
  id                  uuid primary key default gen_random_uuid(),
  id_utilizator       uuid not null references public.profiles (id) on delete cascade,
  id_cont             uuid not null references public.conturi_bancare (id) on delete cascade,

  -- Propunerea clientului: unde vrea sa-i mearga banii ramasi. Adminul o vede si
  -- o poate schimba, dar nu porneste de la o pagina goala — si nici nu muta banii
  -- cuiva fara sa-l fi intrebat.
  id_cont_destinatie  uuid references public.conturi_bancare (id) on delete set null,

  motiv               text,
  status              text not null default 'in_asteptare'
                      check (status in ('in_asteptare', 'aprobata', 'respinsa', 'retrasa')),
  creat_la            timestamptz not null default now(),
  decis_la            timestamptz,
  id_admin            uuid references public.profiles (id) on delete set null,
  motiv_refuz         text
);

comment on table public.cereri_inchidere_cont is
  'Cereri de inchidere a unui cont bancar. Clientul propune contul destinatie, '
  'banca decide si muta banii.';
comment on column public.cereri_inchidere_cont.id_cont_destinatie is
  'Propunerea clientului. Adminul poate alege altul la aprobare.';

-- O singura cerere deschisa PER CONT. Cine a fost respins o data poate cere din
-- nou — de aceea index partial, nu constrangere pe toata coloana.
create unique index if not exists cereri_inchidere_cont_una_deschisa_idx
  on public.cereri_inchidere_cont (id_cont)
  where status = 'in_asteptare';

create index if not exists cereri_inchidere_cont_coada_idx
  on public.cereri_inchidere_cont (status, creat_la);


alter table public.cereri_inchidere_cont enable row level security;

drop policy if exists "cereri inchidere: select" on public.cereri_inchidere_cont;
create policy "cereri inchidere: select"
  on public.cereri_inchidere_cont for select to authenticated
  using (auth.uid() = id_utilizator or public.este_administrator());

drop policy if exists "cereri inchidere: depune" on public.cereri_inchidere_cont;
create policy "cereri inchidere: depune"
  on public.cereri_inchidere_cont for insert to authenticated
  with check (auth.uid() = id_utilizator);

drop policy if exists "cereri inchidere: retrage" on public.cereri_inchidere_cont;
create policy "cereri inchidere: retrage"
  on public.cereri_inchidere_cont for update to authenticated
  using (
    (auth.uid() = id_utilizator and status = 'in_asteptare')
    or public.este_administrator()
  )
  with check (auth.uid() = id_utilizator or public.este_administrator());


create or replace function public.cereri_inchidere_pastreaza_decizia()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- Aceeasi garda ca la 0036, si din acelasi motiv: `with check` nu poate compara
  -- starea veche cu cea noua. Fara trigger, un client si-ar putea scrie
  -- status = 'aprobata' direct prin PostgREST.
  if public.este_administrator() then
    return new;
  end if;

  if new.status is distinct from old.status and new.status <> 'retrasa' then
    raise exception 'DECIZIE_REZERVATA_BANCII'
      using detail = 'Doar banca poate aproba sau respinge o cerere de inchidere.';
  end if;

  new.id_admin    := old.id_admin;
  new.motiv_refuz := old.motiv_refuz;
  new.decis_la    := old.decis_la;
  return new;
end;
$$;

drop trigger if exists cereri_inchidere_before_update on public.cereri_inchidere_cont;
create trigger cereri_inchidere_before_update
  before update on public.cereri_inchidere_cont
  for each row execute function public.cereri_inchidere_pastreaza_decizia();


-- -----------------------------------------------------------------------------
-- 4. Decizia bancii
--
-- Totul intr-o singura tranzactie: ori se muta banii SI se inchide contul SI se
-- inchid cardurile, ori nu se intampla nimic. Un cont inchis peste care banii au
-- ramas, sau bani mutati dintr-un cont ramas deschis, sunt amandoua stari din
-- care nu se iese usor.
-- -----------------------------------------------------------------------------

create or replace function public.inchide_cont_bancar(
  p_id_cerere     uuid,
  p_id_admin      uuid,
  p_id_destinatie uuid default null
)
returns public.cereri_inchidere_cont
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_cerere     public.cereri_inchidere_cont%rowtype;
  v_cont       public.conturi_bancare%rowtype;
  v_destinatie public.conturi_bancare%rowtype;
  v_iban_princ text;
  v_id_dest    uuid;
  v_mutat      numeric(14,2) := 0;
  v_carduri    integer := 0;
  v_mesaj      text;
begin
  select c.* into v_cerere
  from public.cereri_inchidere_cont c
  where c.id = p_id_cerere
  for update;

  if not found then
    raise exception 'CERERE_INEXISTENTA' using detail = 'Cererea nu exista.';
  end if;

  if v_cerere.status <> 'in_asteptare' then
    raise exception 'CERERE_DECISA'
      using detail = 'Cererea a fost deja ' || v_cerere.status || '.';
  end if;

  select c.* into v_cont
  from public.conturi_bancare c
  where c.id = v_cerere.id_cont
  for update;

  if not found then
    raise exception 'CONT_INEXISTENT' using detail = 'Contul nu mai exista.';
  end if;

  if v_cont.inchis_la is not null then
    raise exception 'CONT_DEJA_INCHIS' using detail = 'Contul e deja inchis.';
  end if;

  -- Contul principal ramane. E IBAN-ul pe care clientul il da mai departe si
  -- tinta consolidarii din 0037 — daca ar disparea, plecarea din banca n-ar mai
  -- avea unde sa stranga banii.
  select p.iban_cont into v_iban_princ
  from public.profiles p where p.id = v_cerere.id_utilizator;

  if v_iban_princ is not null and v_cont.iban = v_iban_princ then
    raise exception 'CONT_PRINCIPAL'
      using detail = 'Contul principal nu se poate inchide. Pentru a pleca din banca se inchide relatia.';
  end if;

  if v_cont.blocat_administrativ then
    raise exception 'CONT_BLOCAT'
      using detail = 'Contul e blocat administrativ; se lamureste intai blocarea.';
  end if;

  if v_cont.sold < 0 then
    raise exception 'SOLD_NEGATIV'
      using detail = 'Contul are sold negativ. Se acopera inainte de inchidere.';
  end if;

  -- Destinatia: alegerea adminului, altfel propunerea clientului, altfel contul
  -- principal. Ultima treapta e cea care face optiunea "automat, in contul
  -- curent" din panou sa mearga fara ca adminul sa aleaga ceva.
  v_id_dest := coalesce(p_id_destinatie, v_cerere.id_cont_destinatie);

  if v_id_dest is null and v_iban_princ is not null then
    select c.id into v_id_dest
    from public.conturi_bancare c
    where c.id_user = v_cerere.id_utilizator
      and c.iban = v_iban_princ
      and c.inchis_la is null;
  end if;

  if v_cont.sold > 0 then
    if v_id_dest is null then
      raise exception 'FARA_DESTINATIE'
        using detail = 'Contul are sold, dar nu s-a putut alege un cont in care sa fie mutat.';
    end if;

    if v_id_dest = v_cont.id then
      raise exception 'DESTINATIE_INVALIDA'
        using detail = 'Contul destinatie nu poate fi chiar contul care se inchide.';
    end if;

    select c.* into v_destinatie
    from public.conturi_bancare c
    where c.id = v_id_dest
      and c.id_user = v_cerere.id_utilizator
      and c.inchis_la is null
    for update;

    if not found then
      raise exception 'DESTINATIE_INVALIDA'
        using detail = 'Contul destinatie nu exista, e inchis, sau e al altui client.';
    end if;

    if v_destinatie.blocat_administrativ then
      raise exception 'DESTINATIE_BLOCATA'
        using detail = 'Contul destinatie e blocat; banii n-ar mai putea fi folositi.';
    end if;

    v_mutat := public.muta_sold_intre_conturi(
      v_cont, v_destinatie, 'Transfer inainte de inchiderea contului'
    );
  end if;

  -- Cardurile pleaca odata cu contul. Se si blocheaza, nu doar se marcheaza:
  -- `inchis_la` e informatia adusa de migratia asta, dar `is_blocked` e ce citesc
  -- functiile de plata scrise inaintea ei.
  update public.carduri
     set inchis_la = now(), is_blocked = true, modificat_la = now()
   where id_cont = v_cont.id and inchis_la is null;

  get diagnostics v_carduri = row_count;

  update public.conturi_bancare c
     set inchis_la = now(), modificat_la = now()
   where c.id = v_cont.id;

  update public.cereri_inchidere_cont c
     set status = 'aprobata', decis_la = now(), id_admin = p_id_admin,
         id_cont_destinatie = v_id_dest
   where c.id = p_id_cerere
  returning * into v_cerere;

  v_mesaj := 'Contul "' || v_cont.nume || '" a fost inchis. ';

  if v_mutat > 0 then
    v_mesaj := v_mesaj || 'Am mutat ' || trim(to_char(v_mutat, 'FM999999999990.00')) ||
               ' ' || v_destinatie.valuta || ' in contul "' || v_destinatie.nume || '". ';
  end if;

  if v_carduri > 0 then
    v_mesaj := v_mesaj ||
               case when v_carduri = 1 then 'Cardul legat de el a fost inchis. '
                    else 'Cele ' || v_carduri || ' carduri legate de el au fost inchise. ' end;
  end if;

  v_mesaj := v_mesaj || 'Istoricul tranzactiilor ramane neschimbat.';

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (v_cerere.id_utilizator, 'Contul a fost inchis', v_mesaj, 'succes');

  perform public.anunta_utilizator(
    v_cerere.id_utilizator, 'notificare',
    jsonb_build_object('id_cerere', v_cerere.id, 'status', 'aprobata')
  );

  return v_cerere;
end;
$$;

comment on function public.inchide_cont_bancar(uuid, uuid, uuid) is
  'Aproba o cerere de inchidere: muta soldul in contul ales, inchide cardurile '
  'si marcheaza contul ca inchis. Totul intr-o singura tranzactie.';

revoke all on function public.inchide_cont_bancar(uuid, uuid, uuid) from public, anon, authenticated;
grant execute on function public.inchide_cont_bancar(uuid, uuid, uuid) to service_role;


create or replace function public.respinge_inchidere_cont(
  p_id_cerere uuid,
  p_id_admin  uuid,
  p_motiv     text default null
)
returns public.cereri_inchidere_cont
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_cerere public.cereri_inchidere_cont%rowtype;
  v_nume   text;
begin
  select c.* into v_cerere
  from public.cereri_inchidere_cont c
  where c.id = p_id_cerere
  for update;

  if not found then
    raise exception 'CERERE_INEXISTENTA' using detail = 'Cererea nu exista.';
  end if;

  if v_cerere.status <> 'in_asteptare' then
    raise exception 'CERERE_DECISA'
      using detail = 'Cererea a fost deja ' || v_cerere.status || '.';
  end if;

  select c.nume into v_nume from public.conturi_bancare c where c.id = v_cerere.id_cont;

  update public.cereri_inchidere_cont c
     set status = 'respinsa', decis_la = now(), id_admin = p_id_admin,
         motiv_refuz = nullif(trim(p_motiv), '')
   where c.id = p_id_cerere
  returning * into v_cerere;

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (
    v_cerere.id_utilizator,
    'Cererea de inchidere a contului a fost respinsa',
    coalesce(
      nullif(trim(p_motiv), ''),
      'Cererea de inchidere pentru contul "' || coalesce(v_nume, 'necunoscut') ||
      '" nu a putut fi aprobata. Scrie-ne daca vrei detalii.'
    ),
    'avertisment'
  );

  perform public.anunta_utilizator(
    v_cerere.id_utilizator, 'notificare',
    jsonb_build_object('id_cerere', v_cerere.id, 'status', 'respinsa')
  );

  return v_cerere;
end;
$$;

revoke all on function public.respinge_inchidere_cont(uuid, uuid, text) from public, anon, authenticated;
grant execute on function public.respinge_inchidere_cont(uuid, uuid, text) to service_role;


-- "Inchis, nu sters" nu inseamna nimic daca nimeni nu poate da inapoi. Banii NU
-- se intorc automat — au plecat intr-un cont real si pot fi deja cheltuiti; se
-- redeschide contul gol, iar restul se rezolva cu un transfer obisnuit. Asta se
-- si scrie in notificare, ca omul sa nu-si caute banii degeaba.
create or replace function public.redeschide_cont(
  p_id_cont  uuid,
  p_id_admin uuid
)
returns public.conturi_bancare
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_cont public.conturi_bancare%rowtype;
begin
  update public.conturi_bancare c
     set inchis_la = null, modificat_la = now()
   where c.id = p_id_cont and c.inchis_la is not null
  returning * into v_cont;

  if not found then
    raise exception 'CONT_NEINCHIS'
      using detail = 'Contul nu exista sau nu e inchis.';
  end if;

  update public.carduri
     set inchis_la = null, modificat_la = now()
   where id_cont = p_id_cont and inchis_la is not null;

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (
    v_cont.id_user, 'Contul a fost redeschis',
    'Contul "' || v_cont.nume || '" a fost redeschis. Banii mutati la inchidere nu se ' ||
    'intorc automat — ii poti transfera inapoi cand vrei.',
    'info'
  );

  perform public.anunta_utilizator(
    v_cont.id_user, 'notificare',
    jsonb_build_object('id_cont', v_cont.id, 'status', 'redeschis')
  );

  return v_cont;
end;
$$;

revoke all on function public.redeschide_cont(uuid, uuid) from public, anon, authenticated;
grant execute on function public.redeschide_cont(uuid, uuid) to service_role;

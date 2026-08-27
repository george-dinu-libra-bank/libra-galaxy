-- =============================================================================
-- 0036 — Cuvinte sensibile: transferul suspect se opreste, nu se reporteaza
--
-- Administratorul tine o lista de cuvinte-cheie (spalare de bani, droguri,
-- mita...). Aplicatia scaneaza descrierea transferului inainte sa cheme
-- `core_banking`; daca gaseste ceva, transferul NU mai trece pe acolo, ci prin
-- `transfer_semnalat` de mai jos.
--
-- Diferenta esentiala fata de „marcam plata dupa ce s-a facut": banii nu ajung
-- niciodata la beneficiar pana nu decide un om. Expeditorul e debitat imediat
-- (altfel ar putea cheltui de doua ori aceiasi bani cat timp asteapta decizia),
-- beneficiarul nu e creditat, iar suma sta in suspans pe seama bancii. Asa,
-- „anuleaza" e mereu posibil — pe cand la o stornare de dupa creditare
-- beneficiarul poate sa fi golit deja contul, si n-ai de unde lua banii inapoi.
--
-- Cele trei stari finale sunt simple miscari de sold, in aceeasi tranzactie cu
-- schimbarea statusului:
--
--   flagged   -> accepta   : beneficiarul e creditat        (status acceptata)
--   flagged   -> anuleaza  : expeditorul primeste banii inapoi (status anulata)
--
-- `core_banking` si `core_banking_groups` raman NEATINSE. Drumul semnalat isi
-- reface validarile lor (cont sursa, IBAN, fonduri, conversie) — cost asumat:
-- daca cineva adauga maine o regula in `core_banking`, trebuie adaugata si
-- aici. Alternativa era sa le rescriu pe amandoua, doua functii mari si
-- delicate, ca sa strecor un `if` in mijloc.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Lista de cuvinte — un singur rand, cu un array in el
--
-- Un rand, nu un rand per cuvant: lista se citeste mereu intreaga (scanerul are
-- nevoie de toate cuvintele deodata) si se salveaza mereu intreaga, din
-- ecranul de administrare. Indexul unic pe o expresie constanta e ce tine
-- tabela la un singur rand — fara el, doua salvari concurente ar lasa in urma
-- doua liste si n-ar mai fi clar care e cea reala.
-- -----------------------------------------------------------------------------
create table if not exists public.sensitive_words (
  id            uuid primary key default gen_random_uuid(),
  cuvinte       text[] not null default '{}'::text[],
  creat_la      timestamptz not null default now(),
  actualizat_la timestamptz not null default now(),
  actualizat_de uuid references public.profiles(id)
);

comment on table public.sensitive_words is
  'Cuvintele-cheie dupa care se scaneaza descrierile transferurilor. Un singur rand, cu lista completa in `cuvinte`.';

create unique index if not exists sensitive_words_singleton_idx
  on public.sensitive_words ((true));

alter table public.sensitive_words enable row level security;

-- Drepturile de tabela, explicit: politicile de mai jos filtreaza randurile, dar
-- fara `grant` rolul nici nu ajunge la ele. `anon` nu primeste nimic.
grant select, insert, update, delete on public.sensitive_words to authenticated;
grant all on public.sensitive_words to service_role;
revoke all on public.sensitive_words from anon;

-- Lista e secreta fata de clienti: cine o vede stie exact ce cuvinte sa evite.
-- Scanerul o citeste din aplicatie cu service_role, deci nu are nevoie de
-- politica; aici intra doar administratorii, din ecranul lor.
drop policy if exists "administratorii citesc cuvintele sensibile" on public.sensitive_words;
create policy "administratorii citesc cuvintele sensibile"
  on public.sensitive_words for select
  to authenticated
  using (public.este_administrator());

drop policy if exists "administratorii scriu cuvintele sensibile" on public.sensitive_words;
create policy "administratorii scriu cuvintele sensibile"
  on public.sensitive_words for all
  to authenticated
  using (public.este_administrator())
  with check (public.este_administrator());

-- Un punct de plecare, ca ecranul sa nu fie gol la prima deschidere. `where not
-- exists` in loc de `on conflict`: indexul e pe o expresie, deci nu poate fi
-- tinta unui `on conflict`.
insert into public.sensitive_words (cuvinte)
select array[
  'spalare de bani', 'bani negri', 'bani murdari', 'droguri', 'cocaina',
  'heroina', 'canabis', 'arme', 'munitie', 'contrabanda', 'mita', 'spaga',
  'santaj', 'rascumparare', 'terorism', 'trafic de persoane', 'evaziune'
]::text[]
where not exists (select 1 from public.sensitive_words);


-- -----------------------------------------------------------------------------
-- 2. Starea unei tranzactii
--
-- `normala` e implicita si acopera tot ce exista deja in tabela: cele scrise de
-- `core_banking`, `core_banking_groups` si de operatiunile de credit.
-- -----------------------------------------------------------------------------
alter table public.tranzactii
  add column if not exists status          text not null default 'normala',
  add column if not exists motiv_semnalare text,
  add column if not exists decis_de        uuid references public.profiles(id),
  add column if not exists decis_la        timestamptz;

alter table public.tranzactii drop constraint if exists tranzactii_status_check;
alter table public.tranzactii add constraint tranzactii_status_check
  check (status in ('normala', 'flagged', 'acceptata', 'anulata'));

comment on column public.tranzactii.status is
  'normala = trecuta prin core_banking; flagged = oprita de scaner, banii sunt in suspans; acceptata/anulata = decisa de un administrator.';
comment on column public.tranzactii.motiv_semnalare is
  'Cuvintele gasite in descriere, asa cum apar in lista administratorului.';

-- Coada administratorului: putine randuri dintr-o tabela mare, deci index
-- partial. Ordinea e cea in care se afiseaza.
create index if not exists tranzactii_flagged_idx
  on public.tranzactii (creat_la desc)
  where status = 'flagged';


-- -----------------------------------------------------------------------------
-- 3. Transferul oprit — debiteaza sursa, nu crediteaza beneficiarul
--
-- Aceleasi coduri de eroare ca `core_banking`/`core_banking_groups`, fiindca
-- aplicatia le traduce dintr-un singur dictionar (MESAJE_CORE_BANKING).
--
-- `p_id_user` vine din sesiunea verificata in actiunea de server, iar functia se
-- da doar lui service_role: nu e un RPC pe care sa-l poata chema un client cu
-- id-ul altcuiva.
-- -----------------------------------------------------------------------------
create or replace function public.transfer_semnalat(
  p_id_user      uuid,
  p_iban_dest    text,
  p_suma         numeric,
  p_descriere    text    default null,
  p_id_cont_send uuid    default null,
  p_id_grup_send bigint  default null,
  p_cuvinte      text[]  default '{}'::text[]
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_iban    text;
  v_suma    numeric(14,2);
  v_id_send uuid;
  v_send    public.conturi_bancare%rowtype;
  v_recv    public.conturi_bancare%rowtype;
  v_grup    public.groups%rowtype;
  v_motiv   text;
  v_tranz   public.tranzactii%rowtype;
begin
  if p_id_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat pentru a trimite bani.';
  end if;

  if p_suma is null or p_suma <= 0 or round(p_suma, 2) <> p_suma then
    raise exception 'SUMA_INVALIDA'
      using detail = 'Suma trebuie sa fie mai mare decat 0 si cu cel mult doua zecimale.';
  end if;

  v_suma := round(p_suma, 2);

  v_iban := nullif(upper(regexp_replace(coalesce(p_iban_dest, ''), '\s', '', 'g')), '');

  if v_iban is null or v_iban !~ '^RO[0-9]{2}[A-Z0-9]{20}$' then
    raise exception 'IBAN_INVALID'
      using detail = 'IBAN-ul beneficiarului este invalid.';
  end if;

  select c.* into v_recv from public.conturi_bancare c where c.iban = v_iban;

  if not found then
    raise exception 'BENEFICIAR_INEXISTENT'
      using detail = 'Nu exista niciun cont Galaxy Bank cu acest IBAN.';
  end if;

  v_motiv := nullif(array_to_string(coalesce(p_cuvinte, '{}'::text[]), ', '), '');

  -- ---------------------------------------------------------------------------
  -- Sursa: punga comuna a unui grup, sau un cont al omului
  -- ---------------------------------------------------------------------------
  if p_id_grup_send is not null then
    select g.* into v_grup from public.groups g where g.id = p_id_grup_send;

    if not found then
      raise exception 'GRUP_INEXISTENT' using detail = 'Grupul nu exista.';
    end if;

    if not exists (
      select 1 from public.groups_participants gp
       where gp.id_group = v_grup.id and gp.id_user = p_id_user
    ) then
      raise exception 'NU_ESTI_MEMBRU' using detail = 'Nu faci parte din acest grup.';
    end if;

    perform 1 from public.groups g where g.id = v_grup.id for update;
    select g.* into v_grup from public.groups g where g.id = v_grup.id;

    if v_grup.sold < v_suma then
      raise exception 'FONDURI_INSUFICIENTE_GRUP'
        using detail = format('Soldul grupului: %s RON, suma ceruta: %s RON.',
                              v_grup.sold, v_suma);
    end if;

    update public.groups set sold = sold - v_suma, modificat_la = now()
     where id = v_grup.id;

    -- Soldul comun scade sub ochii tuturor membrilor; le spunem de ce. Mesajul
    -- de tip „plata" se scrie abia daca administratorul accepta, ca sa nu apara
    -- in conversatie o plata care poate fi anulata.
    insert into public.group_messages (continut, id_user, id_group, type)
    values (
      format('%s RON au fost reținuți pentru verificare de către bancă.',
             public.formateaza_suma_ron(v_suma)),
      p_id_user, v_grup.id, 'text'
    );

    insert into public.tranzactii (
      id_user_send, id_group_send, id_user_recieve, id_cont_recieve,
      suma, valuta, descriere, status, motiv_semnalare
    )
    values (
      p_id_user, v_grup.id, v_recv.id_user, v_recv.id,
      v_suma, 'RON', nullif(btrim(coalesce(p_descriere, '')), ''), 'flagged', v_motiv
    )
    returning * into v_tranz;
  else
    if p_id_cont_send is not null then
      select c.id into v_id_send
        from public.conturi_bancare c
       where c.id = p_id_cont_send and c.id_user = p_id_user;

      if v_id_send is null then
        if exists (select 1 from public.conturi_bancare c where c.id = p_id_cont_send) then
          raise exception 'CONT_SURSA_STRAIN'
            using detail = 'Nu poti plati dintr-un cont care nu este al tau.';
        end if;

        raise exception 'CONT_SURSA_INEXISTENT'
          using detail = 'Contul din care vrei sa platesti nu exista.';
      end if;
    else
      select c.id into v_id_send
        from public.conturi_bancare c
       where c.id_user = p_id_user
       order by c.creat_la, c.id
       limit 1;

      if v_id_send is null then
        raise exception 'CONT_SURSA_INEXISTENT'
          using detail = 'Nu ai niciun cont din care sa platesti.';
      end if;
    end if;

    if v_id_send = v_recv.id then
      raise exception 'AUTOTRANSFER'
        using detail = 'Nu poti trimite bani in acelasi cont din care platesti.';
    end if;

    -- Se atinge un singur cont (beneficiarul nu e creditat aici), deci un
    -- singur lock — n-are cum sa apara ordinea incrucisata din `core_banking`.
    perform 1 from public.conturi_bancare c where c.id = v_id_send for update;
    select c.* into v_send from public.conturi_bancare c where c.id = v_id_send;

    if v_send.sold < v_suma then
      raise exception 'FONDURI_INSUFICIENTE'
        using detail = format('Sold disponibil: %s %s, suma ceruta: %s %s.',
                              v_send.sold, v_send.valuta, v_suma, v_send.valuta);
    end if;

    -- Triggerul din 0030 opreste aici transferul dintr-un cont blocat.
    update public.conturi_bancare set sold = sold - v_suma, modificat_la = now()
     where id = v_send.id;

    insert into public.tranzactii (
      id_user_send, id_user_recieve, id_cont_send, id_cont_recieve,
      suma, valuta, descriere, status, motiv_semnalare
    )
    values (
      p_id_user, v_recv.id_user, v_send.id, v_recv.id,
      v_suma, v_send.valuta, nullif(btrim(coalesce(p_descriere, '')), ''), 'flagged', v_motiv
    )
    returning * into v_tranz;
  end if;

  return jsonb_build_object(
    'id_tranzactie', v_tranz.id,
    'status',        v_tranz.status,
    'suma',          v_tranz.suma,
    'valuta',        v_tranz.valuta,
    'motiv',         v_motiv
  );
end;
$$;

comment on function public.transfer_semnalat is
  'Transfer oprit de scanerul de cuvinte: debiteaza sursa, nu crediteaza beneficiarul, scrie tranzactia cu status flagged.';

revoke all on function public.transfer_semnalat(uuid, text, numeric, text, uuid, bigint, text[])
  from public, anon, authenticated;
grant execute on function public.transfer_semnalat(uuid, text, numeric, text, uuid, bigint, text[])
  to service_role;


-- -----------------------------------------------------------------------------
-- 4. Decizia administratorului
--
-- `for update` pe randul tranzactiei, apoi verificarea statusului: doi
-- administratori care apasa in acelasi timp nu pot credita beneficiarul de doua
-- ori — al doilea gaseste randul deja decis si primeste DEJA_DECISA.
-- -----------------------------------------------------------------------------
create or replace function public.decide_transfer_semnalat(
  p_id       uuid,
  p_decizie  text,
  p_id_admin uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_decizie text := lower(btrim(coalesce(p_decizie, '')));
  v_tranz   public.tranzactii%rowtype;
  v_recv    public.conturi_bancare%rowtype;
  v_send    public.conturi_bancare%rowtype;
  v_grup    public.groups%rowtype;
  v_primit  numeric(14,2);
  v_status  text;
begin
  if v_decizie not in ('accepta', 'anuleaza') then
    raise exception 'DECIZIE_INVALIDA'
      using detail = 'Decizia poate fi doar „accepta" sau „anuleaza".';
  end if;

  select t.* into v_tranz from public.tranzactii t where t.id = p_id for update;

  if not found then
    raise exception 'TRANZACTIE_INEXISTENTA' using detail = 'Tranzactia nu exista.';
  end if;

  if v_tranz.status <> 'flagged' then
    raise exception 'DEJA_DECISA'
      using detail = format('Tranzactia are deja starea „%s".', v_tranz.status);
  end if;

  if v_decizie = 'accepta' then
    select c.* into v_recv
      from public.conturi_bancare c
     where c.id = v_tranz.id_cont_recieve
       for update;

    if not found then
      raise exception 'CONT_BENEFICIAR_INEXISTENT'
        using detail = 'Contul beneficiarului nu mai exista; transferul poate fi doar anulat.';
    end if;

    -- Conversia se face acum, la cursul de azi: banii n-au plecat pana acum.
    v_primit := public.converteste(v_tranz.suma, v_tranz.valuta, v_recv.valuta);

    if v_primit <= 0 then
      raise exception 'SUMA_PREA_MICA'
        using detail = 'Suma e prea mica pentru a ajunge in valuta beneficiarului.';
    end if;

    update public.conturi_bancare set sold = sold + v_primit, modificat_la = now()
     where id = v_recv.id;

    -- Abia acum plata devine reala si pentru conversatia grupului.
    if v_tranz.id_group_send is not null then
      insert into public.group_messages (continut, id_user, id_group, type)
      values (
        format('%s RON au ieșit din grup, după verificarea băncii.',
               public.formateaza_suma_ron(v_tranz.suma)),
        v_tranz.id_user_send, v_tranz.id_group_send, 'plata'
      );
    end if;

    v_status := 'acceptata';
  else
    -- Banii se intorc de unde au plecat. Un cont blocat poate PRIMI bani
    -- (0030), deci restituirea merge si daca intre timp contul a fost oprit.
    if v_tranz.id_group_send is not null then
      select g.* into v_grup from public.groups g where g.id = v_tranz.id_group_send for update;

      if not found then
        raise exception 'GRUP_INEXISTENT'
          using detail = 'Grupul din care au plecat banii nu mai exista.';
      end if;

      update public.groups set sold = sold + v_tranz.suma, modificat_la = now()
       where id = v_grup.id;

      insert into public.group_messages (continut, id_user, id_group, type)
      values (
        format('%s RON s-au întors în grup: banca a anulat plata.',
               public.formateaza_suma_ron(v_tranz.suma)),
        v_tranz.id_user_send, v_grup.id, 'incasare'
      );
    else
      select c.* into v_send
        from public.conturi_bancare c
       where c.id = v_tranz.id_cont_send
         for update;

      if not found then
        raise exception 'CONT_SURSA_INEXISTENT'
          using detail = 'Contul din care au plecat banii nu mai exista.';
      end if;

      update public.conturi_bancare set sold = sold + v_tranz.suma, modificat_la = now()
       where id = v_send.id;
    end if;

    v_status := 'anulata';
  end if;

  update public.tranzactii
     set status   = v_status,
         decis_de = p_id_admin,
         decis_la = now()
   where id = v_tranz.id
   returning * into v_tranz;

  -- Omul care a trimis banii trebuie sa afle ce s-a intamplat cu ei.
  if v_tranz.id_user_send is not null then
    insert into public.notificari (id_utilizator, titlu, mesaj, tip)
    values (
      v_tranz.id_user_send,
      case when v_status = 'acceptata' then 'Transfer eliberat' else 'Transfer anulat' end,
      case
        when v_status = 'acceptata' then
          format('Transferul de %s %s a trecut de verificarea băncii și a ajuns la beneficiar.',
                 v_tranz.suma, v_tranz.valuta)
        else
          format('Transferul de %s %s a fost anulat de bancă, iar suma ți-a fost returnată.',
                 v_tranz.suma, v_tranz.valuta)
      end,
      case when v_status = 'acceptata' then 'info' else 'atentionare' end
    );
  end if;

  return jsonb_build_object(
    'id_tranzactie', v_tranz.id,
    'status',        v_tranz.status,
    'suma',          v_tranz.suma,
    'valuta',        v_tranz.valuta,
    'suma_primita',  v_primit
  );
end;
$$;

comment on function public.decide_transfer_semnalat is
  'Elibereaza sau anuleaza un transfer cu status flagged: crediteaza beneficiarul, respectiv restituie sursa.';

revoke all on function public.decide_transfer_semnalat(uuid, text, uuid)
  from public, anon, authenticated;
grant execute on function public.decide_transfer_semnalat(uuid, text, uuid)
  to service_role;

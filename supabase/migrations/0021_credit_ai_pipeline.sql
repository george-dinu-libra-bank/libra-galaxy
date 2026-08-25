-- =============================================================================
-- Libra — pipeline AI de creditare: observatii consultative peste dosarul deja
-- decis determinist de credit_service.py + scorecard.py.
--
-- Migrarea NU atinge nimic din motorul de decizie existent (credit_cereri,
-- credit_verificari_venit, scorecard). Adauga trei tabele noi, scrise exclusiv
-- de service_role, care tin evidenta rularilor pipeline-ului, etapa cu etapa,
-- si semnalele pe care le-a gasit. Niciun camp de aici nu e citit vreodata de
-- reguli.py sau scorecard.py — legatura e strict intr-un singur sens.
--
-- Verificat inainte de scriere (REGULI.md #3): 0017 e ultima migratie aplicata,
-- credit_documente si credit_cereri au exact coloanele din 0009+0015+0016.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. O rulare a pipeline-ului, per cerere
--
-- `intrare_hash` e sha256 peste datele de intrare ale rularii (cerere +
-- verificari + documente la momentul declansarii). O rulare reusita cu acelasi
-- hash se refoloseste in loc sa se recheme modelul — vezi lazy catch-up in
-- CreditAiPipeline.
--
-- `recomandare` vine din etapa 'brief' si e ce se compara cu decizia finala a
-- omului pe pagina de observabilitate (credit_ai_acord, mai jos). Nu e o
-- decizie: e o parere, si ramane asa in nume.
-- -----------------------------------------------------------------------------
create table if not exists public.credit_ai_rulari (
  id                 uuid primary key default gen_random_uuid(),
  id_cerere          uuid        not null references public.credit_cereri (id) on delete cascade,
  declansator        text        not null,
  status             text        not null default 'in_curs',
  versiune_pipeline  text        not null,
  recomandare        text,
  incredere          numeric(4,3),
  intrare_hash       text        not null,
  latenta_ms         integer,
  cost_estimat_usd   numeric(10,6) not null default 0,
  creat_la           timestamptz not null default now(),
  finalizat_la       timestamptz,

  constraint credit_ai_rulari_declansator_check check (declansator in (
    'evalueaza', 'document_incarcat', 'document_confirmat', 'lazy', 'manual'
  )),
  constraint credit_ai_rulari_status_check check (status in ('in_curs', 'finalizat', 'esuat')),
  constraint credit_ai_rulari_recomandare_check check (recomandare is null or recomandare in (
    'aproba', 'respinge', 'cere_document', 'fara_recomandare'
  )),
  constraint credit_ai_rulari_incredere_check check (incredere is null or incredere between 0 and 1)
);

comment on table public.credit_ai_rulari is
  'O rulare a pipeline-ului AI de credite. Strict consultativ: nu exista nicio coloana aici care sa fie citita de motorul de scoring.';
comment on column public.credit_ai_rulari.intrare_hash is
  'sha256 peste datele de intrare. O rulare reusita cu acelasi hash se refoloseste, nu se recheama modelul.';
comment on column public.credit_ai_rulari.recomandare is
  'Parerea etapei de brief, comparata ulterior cu decizia omului (vezi view-ul credit_ai_acord). Niciodata scrisa in credit_cereri.';

create index if not exists credit_ai_rulari_cerere_idx on public.credit_ai_rulari (id_cerere, creat_la desc);


-- -----------------------------------------------------------------------------
-- 2. Etapele unei rulari
--
-- O rulare are pana la patru randuri aici, unul per etapa. O etapa esuata nu
-- opreste celelalte — fiecare e independenta, exact ca sursele de venit din
-- credit_verificari_venit.
-- -----------------------------------------------------------------------------
create table if not exists public.credit_ai_etape (
  id                uuid primary key default gen_random_uuid(),
  id_rulare         uuid        not null references public.credit_ai_rulari (id) on delete cascade,
  etapa             text        not null,
  status            text        not null,
  versiune_prompt   text,
  deployment        text,
  rezultat          jsonb       not null default '{}'::jsonb,
  incredere         numeric(4,3),
  latenta_ms        integer,
  tokeni_intrare    integer     not null default 0,
  tokeni_iesire     integer     not null default 0,
  tokeni_cache      integer     not null default 0,
  cod_eroare        text,
  creat_la          timestamptz not null default now(),

  constraint credit_ai_etape_etapa_check check (etapa in ('documente', 'coerenta', 'brief', 'explicatie')),
  constraint credit_ai_etape_status_check check (status in ('reusit', 'esuat', 'sarit')),
  constraint credit_ai_etape_incredere_check check (incredere is null or incredere between 0 and 1)
);

comment on table public.credit_ai_etape is
  'O etapa dintr-o rulare a pipeline-ului. `coerenta` nu are model (deployment/tokeni raman null) — e determinista, testata ca reguli.py.';

create index if not exists credit_ai_etape_rulare_idx on public.credit_ai_etape (id_rulare);


-- -----------------------------------------------------------------------------
-- 3. Semnalele gasite — ce vede analistul
--
-- Legate si de cerere, si de rularea care le-a produs: cererea, ca lista se
-- poate afisa fara sa se stie care rulare a fost cea buna; rularea, ca o
-- semnalare veche sa poata fi distinsa de una noua dupa o reevaluare.
-- -----------------------------------------------------------------------------
create table if not exists public.credit_ai_semnale (
  id           uuid primary key default gen_random_uuid(),
  id_cerere    uuid        not null references public.credit_cereri (id) on delete cascade,
  id_rulare    uuid        not null references public.credit_ai_rulari (id) on delete cascade,
  cod          text        not null,
  severitate   text        not null,
  titlu        text        not null,
  detaliu      jsonb       not null default '{}'::jsonb,
  sursa        text        not null,
  creat_la     timestamptz not null default now(),

  constraint credit_ai_semnale_severitate_check check (severitate in ('grav', 'atentie', 'informativ')),
  constraint credit_ai_semnale_sursa_check check (sursa in ('coerenta', 'documente', 'brief'))
);

comment on table public.credit_ai_semnale is
  'Semnale consultative pentru analist. `sursa` = coerenta inseamna determinist, fara model — acelea sunt cele mai de incredere.';

create index if not exists credit_ai_semnale_cerere_idx on public.credit_ai_semnale (id_cerere, creat_la desc);


-- -----------------------------------------------------------------------------
-- 4. Documentul reutilizat e ieftin de detectat doar cu un index pe hash
--
-- Partial: majoritatea documentelor incarcate dupa 0015 au hash_fisier populat,
-- dar cateva randuri istorice dinainte pot fi null — indexul nu are ce cauta cu
-- ele.
-- -----------------------------------------------------------------------------
create index if not exists credit_documente_hash_idx
  on public.credit_documente (hash_fisier)
  where hash_fisier is not null;


-- -----------------------------------------------------------------------------
-- 5. Securitate — acelasi tipar ca agent_runs/tool_invocations/ai_usage_records
-- si credit_bureau_simulat (0004, 0009): RLS activat, nicio politica pentru
-- 'authenticated'. Datele sunt pentru analist, si ajung la el prin backend cu
-- service_role — care ocoleste RLS — niciodata direct din client.
-- -----------------------------------------------------------------------------
alter table public.credit_ai_rulari  enable row level security;
alter table public.credit_ai_etape   enable row level security;
alter table public.credit_ai_semnale enable row level security;


-- -----------------------------------------------------------------------------
-- 6. Read models pentru dashboard-ul de observabilitate (ARCHITECTURE.md #9)
--
-- supabase-py nu face GROUP BY; agregarea traieste in baza, ca sa nu se aduca
-- randuri brute doar ca sa fie insumate in Python.
--
-- security_invoker: view-urile respecta RLS-ul tabelelor de dedesubt pentru
-- oricine le-ar interoga — desi azi doar service_role o face (bypasseaza RLS
-- oricum), e disciplina corecta sa nu depinda de asta.
-- -----------------------------------------------------------------------------
create or replace view public.credit_ai_rezumat_zilnic
  with (security_invoker = true) as
select
  date_trunc('day', e.creat_la)::date as zi,
  e.etapa,
  count(*) filter (where e.status = 'reusit')                 as reusite,
  count(*) filter (where e.status = 'esuat')                   as esuate,
  count(*) filter (where e.status = 'sarit')                    as sarite,
  round(avg(e.latenta_ms) filter (where e.status = 'reusit'))   as latenta_medie_ms,
  percentile_cont(0.95) within group (order by e.latenta_ms)
    filter (where e.status = 'reusit')                          as latenta_p95_ms,
  sum(e.tokeni_intrare)  as tokeni_intrare,
  sum(e.tokeni_iesire)   as tokeni_iesire
from public.credit_ai_etape e
group by 1, 2;

comment on view public.credit_ai_rezumat_zilnic is
  'Rulari si esecuri pe etapa, pe zi. `coerenta` nu are model, deci ar trebui sa fie mereu 100% reusita — orice esec acolo e un bug, nu un raspuns rau de la Foundry.';

create or replace view public.credit_ai_acord
  with (security_invoker = true) as
select
  r.id           as id_rulare,
  r.id_cerere,
  r.recomandare,
  r.incredere,
  c.status       as decizie_finala,
  case
    when r.recomandare = 'aproba'   and c.status = 'acceptata' then true
    when r.recomandare = 'respinge' and c.status = 'respinsa'  then true
    when r.recomandare in ('aproba', 'respinge')
     and c.status in ('acceptata', 'respinsa')                 then false
    else null
  end as de_acord
from public.credit_ai_rulari r
join public.credit_cereri c on c.id = r.id_cerere
where r.recomandare is not null
  and c.status in ('acceptata', 'respinsa');

comment on view public.credit_ai_acord is
  'Recomandarea etapei de brief vs. decizia finala luata de om. Rata de "de_acord" arata daca pipeline-ul chiar ajuta sau doar zgomot.';

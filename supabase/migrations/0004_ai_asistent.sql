-- =============================================================================
-- Libra — asistent AI: conversatii, memorie, RAG, telemetrie
--
-- Aditiva: nu atinge profiles/conturi_bancare/tranzactii/groups. Backend-ul
-- FastAPI (service_role) e singurul care scrie in tabelele de cunoastere si
-- telemetrie; conversatiile/mesajele/memoriile sunt scrise tot din backend
-- (service_role), dar RLS le limiteaza la citire pentru proprietarul lor, ca
-- un client care ar obtine din greseala cheia anon sa nu poata citi la altii.
--
-- Patru familii de stare, separate ca sa nu se amestece intamplator:
--   1. conversatii/mesaje/memorie   — recolectare, nu adevar bancar
--   2. cunoastere (RAG)             — referinta citata, partajata
--   3. cache de embeddinguri        — cache, nu arhiva
--   4. telemetrie AI                — jurnal intern, fara continut de mesaj
-- =============================================================================

create extension if not exists vector;

-- -----------------------------------------------------------------------------
-- 1. Conversatii si mesaje
-- -----------------------------------------------------------------------------
create table if not exists public.ai_conversations (
  id                 uuid primary key default gen_random_uuid(),
  id_user            uuid        not null references public.profiles (id) on delete cascade,
  titlu              text        not null default 'Conversație nouă',
  summary_watermark  integer     not null default 0,
  creat_la           timestamptz not null default now(),
  actualizat_la      timestamptz not null default now(),

  constraint ai_conversations_watermark_check check (summary_watermark >= 0)
);

comment on table public.ai_conversations is 'O sesiune de chat cu asistentul, detinuta de un singur utilizator.';
comment on column public.ai_conversations.summary_watermark is 'Numarul de secventa pana la care rezumatul acopera deja mesajele (compresie incrementala).';

create index if not exists ai_conversations_id_user_idx on public.ai_conversations (id_user, actualizat_la desc);

create table if not exists public.ai_messages (
  id              uuid primary key default gen_random_uuid(),
  id_conversation uuid        not null references public.ai_conversations (id) on delete cascade,
  id_user         uuid        not null references public.profiles (id) on delete cascade,
  secventa        integer     not null,
  rol             text        not null,
  continut        text        not null,
  citari          jsonb       not null default '[]'::jsonb,
  creat_la        timestamptz not null default now(),

  constraint ai_messages_rol_check      check (rol in ('user', 'assistant')),
  constraint ai_messages_secventa_check check (secventa >= 1),
  constraint ai_messages_unic_secventa  unique (id_conversation, secventa)
);

comment on table public.ai_messages is 'Mesajele unei conversatii, in ordinea secventei. Continutul nu se logheaza in telemetrie (docs/SECURITY.md).';
comment on column public.ai_messages.citari is 'Lista de citate din knowledge_chunks care sustin raspunsul asistentului, goala pentru mesajele utilizatorului.';

create index if not exists ai_messages_conversation_idx on public.ai_messages (id_conversation, secventa);

create table if not exists public.ai_conversation_summaries (
  id_conversation          uuid primary key references public.ai_conversations (id) on delete cascade,
  id_user                  uuid        not null references public.profiles (id) on delete cascade,
  rezumat                  text        not null default '',
  acopera_pana_la_secventa integer     not null default 0,
  actualizat_la            timestamptz not null default now()
);

comment on table public.ai_conversation_summaries is 'Rezumatul determinist al mesajelor mai vechi decat fereastra recenta, actualizat incremental.';

-- -----------------------------------------------------------------------------
-- 2. Memorie de utilizator (preferinte, nu stare bancara)
-- -----------------------------------------------------------------------------
create table if not exists public.ai_user_memories (
  id         uuid primary key default gen_random_uuid(),
  id_user    uuid        not null references public.profiles (id) on delete cascade,
  tip        text        not null,
  continut   text        not null,
  expira_la  timestamptz,
  creat_la   timestamptz not null default now(),

  constraint ai_user_memories_tip_check check (tip in ('preferinta', 'intentie_declarata', 'fapt_conversational'))
);

comment on table public.ai_user_memories is 'Memorie per utilizator, expirabila. Nu este niciodata sursa de adevar pentru solduri sau tranzactii (docs/AI_ARCHITECTURE.md #6).';

create index if not exists ai_user_memories_id_user_idx on public.ai_user_memories (id_user);

-- -----------------------------------------------------------------------------
-- 3. Cunoastere (RAG) — partajata, fara proprietar
-- -----------------------------------------------------------------------------
create table if not exists public.knowledge_documents (
  document_id    text        not null,
  versiune       integer     not null default 1,
  sursa          text        not null,
  tip_document   text        not null,
  limba          text        not null default 'ro',
  checksum       text        not null,
  audienta       text        not null default 'customer',
  actualizat_la  timestamptz not null default now(),

  primary key (document_id, versiune),
  constraint knowledge_documents_audienta_check check (audienta in ('customer', 'staff'))
);

comment on table public.knowledge_documents is 'Registrul documentelor din galaxy-bank-knowledge, cu versiune si checksum pentru reindexare incrementala.';

create table if not exists public.knowledge_chunks (
  id             uuid primary key default gen_random_uuid(),
  embedding_key  text         not null,
  chunk_id       text         not null,
  document_id    text         not null,
  versiune       integer      not null,
  sectiune       text,
  continut       text         not null,
  embedding      vector(1536) not null,
  metadata       jsonb        not null default '{}'::jsonb,
  creat_la       timestamptz  not null default now(),

  constraint knowledge_chunks_unic unique (embedding_key, chunk_id)
);

comment on table public.knowledge_chunks is 'Fragmente indexate ale bazei de cunostinte. chunk_id e adresat prin continut (sha256), asa incat reindexarea e incrementala.';
comment on column public.knowledge_chunks.embedding_key is 'provider:deployment:versiune_embedding — vectorii din chei diferite nu se compara niciodata.';

create index if not exists knowledge_chunks_embedding_key_idx on public.knowledge_chunks (embedding_key);
create index if not exists knowledge_chunks_document_idx on public.knowledge_chunks (document_id, versiune);

-- -----------------------------------------------------------------------------
-- 4. Cache de embeddinguri — cache, nu arhiva
-- -----------------------------------------------------------------------------
create table if not exists public.embedding_cache (
  cache_key  text primary key,
  embedding  vector(1536) not null,
  creat_la   timestamptz  not null default now()
);

comment on table public.embedding_cache is 'Cache de embeddinguri de chunk, cheie = sha256(embedding_key, continut). Curatat periodic dupa 30 de zile.';

create table if not exists public.query_embedding_cache (
  query_hash     text primary key,
  embedding_key  text         not null,
  embedding      vector(1536) not null,
  creat_la       timestamptz  not null default now()
);

comment on table public.query_embedding_cache is 'Cache de embeddinguri de interogare, cheie = sha256(embedding_key, intrebare). Intrebarea insasi nu se stocheaza.';

-- -----------------------------------------------------------------------------
-- 5. Telemetrie AI — fara continut de mesaj
-- -----------------------------------------------------------------------------
create table if not exists public.agent_runs (
  id                uuid primary key default gen_random_uuid(),
  id_user           uuid references public.profiles (id) on delete set null,
  id_conversation   uuid references public.ai_conversations (id) on delete set null,
  id_agent          text        not null,
  intentie          text,
  nivel_risc        text,
  versiune_prompt   text,
  deployment        text,
  latenta_ms        integer,
  numar_tool_uri    integer     not null default 0,
  fragmente_regasite integer    not null default 0,
  context_caractere integer,
  succes            boolean     not null,
  cod_eroare        text,
  creat_la          timestamptz not null default now()
);

comment on table public.agent_runs is 'O rulare a orchestratorului per tura de conversatie. Fara intrebare/raspuns (docs/SECURITY.md).';

create index if not exists agent_runs_id_user_idx on public.agent_runs (id_user, creat_la desc);

create table if not exists public.tool_invocations (
  id                uuid primary key default gen_random_uuid(),
  id_run            uuid        not null references public.agent_runs (id) on delete cascade,
  nume_tool         text        not null,
  succes            boolean     not null,
  durata_ms         integer,
  motiv_selectie    text,
  creat_la          timestamptz not null default now()
);

comment on table public.tool_invocations is 'Fiecare tool rulat intr-un agent_run, cu motivul selectiei (auditabil).';

create index if not exists tool_invocations_id_run_idx on public.tool_invocations (id_run);

create table if not exists public.ai_usage_records (
  id                 uuid primary key default gen_random_uuid(),
  produs_la          timestamptz not null default now(),
  feature            text        not null,
  id_agent           text,
  deployment         text,
  environment        text        not null default 'local',
  tokeni_intrare     integer     not null default 0,
  tokeni_iesire      integer     not null default 0,
  tokeni_cache       integer     not null default 0,
  cost_estimat_usd   numeric(10,6) not null default 0
);

comment on table public.ai_usage_records is 'Tokeni si cost estimat, atribuite pe feature/agent/deployment. Fara date de client.';

create index if not exists ai_usage_records_produs_la_idx on public.ai_usage_records (produs_la desc);

-- -----------------------------------------------------------------------------
-- 6. RLS
-- -----------------------------------------------------------------------------
alter table public.ai_conversations         enable row level security;
alter table public.ai_messages              enable row level security;
alter table public.ai_conversation_summaries enable row level security;
alter table public.ai_user_memories         enable row level security;
alter table public.knowledge_documents      enable row level security;
alter table public.knowledge_chunks         enable row level security;
alter table public.embedding_cache          enable row level security;
alter table public.query_embedding_cache    enable row level security;
alter table public.agent_runs               enable row level security;
alter table public.tool_invocations         enable row level security;
alter table public.ai_usage_records         enable row level security;

-- Conversatii/mesaje/rezumate/memorie: citire proprie. Scrierea vine din
-- backend cu service_role, care ocoleste RLS — nu exista politici de insert
-- pentru rolul authenticated, la fel ca la sold_curent pe carduri.
drop policy if exists "conversatii proprii: select" on public.ai_conversations;
create policy "conversatii proprii: select"
  on public.ai_conversations for select to authenticated
  using (auth.uid() = id_user);

drop policy if exists "mesaje proprii: select" on public.ai_messages;
create policy "mesaje proprii: select"
  on public.ai_messages for select to authenticated
  using (auth.uid() = id_user);

drop policy if exists "rezumate proprii: select" on public.ai_conversation_summaries;
create policy "rezumate proprii: select"
  on public.ai_conversation_summaries for select to authenticated
  using (auth.uid() = id_user);

drop policy if exists "memorii proprii: select" on public.ai_user_memories;
create policy "memorii proprii: select"
  on public.ai_user_memories for select to authenticated
  using (auth.uid() = id_user);

-- Cunoastere: citire pentru orice utilizator autentificat; scrierea e doar
-- din backend (reindexare). Filtrarea pe audienta ('staff' vs 'customer')
-- ramane responsabilitatea interogarii din backend, nu a RLS.
drop policy if exists "cunoastere: select" on public.knowledge_documents;
create policy "cunoastere: select"
  on public.knowledge_documents for select to authenticated
  using (true);

drop policy if exists "fragmente cunoastere: select" on public.knowledge_chunks;
create policy "fragmente cunoastere: select"
  on public.knowledge_chunks for select to authenticated
  using (true);

-- Cache-urile si telemetria nu au nicio politica pentru authenticated: doar
-- service_role (care ocoleste RLS) le poate citi sau scrie.

grant select on public.ai_conversations, public.ai_messages,
  public.ai_conversation_summaries, public.ai_user_memories,
  public.knowledge_documents, public.knowledge_chunks
  to authenticated;

-- -----------------------------------------------------------------------------
-- 7. Cautare semantica
--
-- Filtrele (embedding_key, limba, tip_document, audienta) se aplica in clauza
-- WHERE, inainte de ordonarea dupa distanta — un scor mare nu poate ocoli un
-- filtru de izolare (docs/AI_ARCHITECTURE.md #7).
-- -----------------------------------------------------------------------------
create or replace function public.match_knowledge_chunks(
  p_embedding_key   text,
  p_query_embedding vector(1536),
  p_languages       text[]  default null,
  p_document_types  text[]  default null,
  p_audience        text    default 'customer',
  p_match_count     integer default 6,
  p_min_score       double precision default 0.5
)
returns table (
  chunk_id    text,
  document_id text,
  versiune    integer,
  sectiune    text,
  continut    text,
  metadata    jsonb,
  scor        double precision
)
language sql
stable
-- 'public', nu '' ca la restul functiilor din schema: operatorul <=> al pgvector
-- traieste in public (unde a creat-o extensia), iar cu search_path gol niciun
-- nume nu se rezolva, nici macar cel al operatorului — desi tipul vector insusi
-- rezolva oricum, fiind legat la definirea tabelei, nu la apelul functiei.
set search_path = 'public'
as $$
  select
    kc.chunk_id,
    kc.document_id,
    kc.versiune,
    kc.sectiune,
    kc.continut,
    kc.metadata,
    1 - (kc.embedding <=> p_query_embedding) as scor
  from public.knowledge_chunks kc
  join public.knowledge_documents kd
    on kd.document_id = kc.document_id and kd.versiune = kc.versiune
  where kc.embedding_key = p_embedding_key
    and kd.audienta in ('customer', p_audience)
    and (p_languages is null or kd.limba = any (p_languages))
    and (p_document_types is null or kd.tip_document = any (p_document_types))
    and (1 - (kc.embedding <=> p_query_embedding)) >= p_min_score
  order by kc.embedding <=> p_query_embedding
  limit greatest(p_match_count, 0);
$$;

comment on function public.match_knowledge_chunks is 'Cautare prin distanta cosinus, cu filtre de izolare aplicate inainte de similaritate.';

grant execute on function public.match_knowledge_chunks to authenticated;

-- -----------------------------------------------------------------------------
-- Optimizari RAG: filtrare pe categorie + cautare hibrida (vector + text)
--
-- 1. knowledge_documents.categorie — derivata automat din knowledge_documents.sursa
--    (primul segment de cale, adica folderul din galaxy-bank-knowledge), NU din
--    frontmatter-ul fiecarui fisier .md. Frontmatter-ul poate diverge de folder
--    (verificat live: fisierele din grupuri/ aveau initial categorie: plăți/
--    conturi-si-utilizatori/securitate/economii, in loc de "grupuri") — o coloana
--    generata din calea deja stocata e imuna la acest gen de neconcordanta si nu
--    cere nicio modificare in pipeline-ul de ingestie (registry.py/reindex_knowledge.py).
--
-- 2. knowledge_chunks.continut_tsv — vector de cautare full-text (configuratie
--    'romanian', corpusul e predominant in romana), cu index GIN. Foloseste ca
--    plasa de siguranta langa cautarea vectoriala: un termen exact (nume de produs,
--    cifra) poate iesi cu scor semantic sub prag, dar tot trebuie sa apara daca
--    se potriveste exact la cautare full-text.
--
-- 3. match_knowledge_chunks — extinsa cu p_query_text (pentru full-text) si
--    p_categories (filtru de izolare, aplicat in WHERE ca si celelalte filtre,
--    inainte de scor — docs/AI_ARCHITECTURE.md #7). Ordonarea ramane primar dupa
--    scorul vectorial (comportament neschimbat pentru cazul comun); un chunk
--    care trece doar pragul full-text, dar nu si p_min_score semantic, e inclus
--    totusi in candidati — altfel plasa de siguranta n-ar avea niciun efect.
-- -----------------------------------------------------------------------------

alter table public.knowledge_documents
  add column if not exists categorie text generated always as (split_part(sursa, '/', 1)) stored;

comment on column public.knowledge_documents.categorie is
  'Categoria documentului = primul segment din sursa (numele folderului din galaxy-bank-knowledge), derivata automat — nu depinde de frontmatter-ul fiecarui fisier.';

create index if not exists knowledge_documents_categorie_idx on public.knowledge_documents (categorie);

alter table public.knowledge_chunks
  add column if not exists continut_tsv tsvector generated always as (to_tsvector('romanian', continut)) stored;

comment on column public.knowledge_chunks.continut_tsv is
  'Index full-text (configuratie romanian) — plasa de siguranta langa cautarea vectoriala pentru termeni exacti (nume de produs, cifre) care pot iesi cu scor semantic scazut.';

create index if not exists knowledge_chunks_continut_tsv_idx on public.knowledge_chunks using gin (continut_tsv);

-- CREATE OR REPLACE nu inlocuieste o functie cu semnatura diferita (Postgres
-- o trateaza ca supraincarcare, dupa numarul/tipurile parametrilor, nu dupa
-- nume) — cu 2 parametri noi adaugati, ar ramane si vechea functie cu 7
-- parametri, ambigua pentru PostgREST la apelul din supabase-py. DROP explicit
-- pe semnatura veche, apoi CREATE curat.
drop function if exists public.match_knowledge_chunks(
  text, vector(1536), text[], text[], text, integer, double precision
);

create or replace function public.match_knowledge_chunks(
  p_embedding_key   text,
  p_query_embedding vector(1536),
  p_languages       text[]  default null,
  p_document_types  text[]  default null,
  p_audience        text    default 'customer',
  p_match_count     integer default 6,
  p_min_score       double precision default 0.5,
  p_query_text      text    default null,
  p_categories      text[]  default null
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
  with candidati as (
    select
      kc.chunk_id,
      kc.document_id,
      kc.versiune,
      kc.sectiune,
      kc.continut,
      kc.metadata,
      1 - (kc.embedding <=> p_query_embedding) as scor,
      (
        p_query_text is not null
        and kc.continut_tsv @@ websearch_to_tsquery('romanian', p_query_text)
      ) as potrivire_text
    from public.knowledge_chunks kc
    join public.knowledge_documents kd
      on kd.document_id = kc.document_id and kd.versiune = kc.versiune
    where kc.embedding_key = p_embedding_key
      and kd.audienta in ('customer', p_audience)
      and (p_languages is null or kd.limba = any (p_languages))
      and (p_document_types is null or kd.tip_document = any (p_document_types))
      and (p_categories is null or kd.categorie = any (p_categories))
  )
  select chunk_id, document_id, versiune, sectiune, continut, metadata, scor
  from candidati
  -- Comportament neschimbat pentru cazul comun (fara p_query_text): doar
  -- pragul semantic. Cu p_query_text, un chunk care se potriveste exact la
  -- full-text trece si daca scorul semantic e sub prag — plasa de siguranta
  -- pentru termeni exacti (nume de produs, cifre) prost acoperiti semantic.
  where scor >= p_min_score or potrivire_text
  order by scor desc
  limit greatest(p_match_count, 0);
$$;

comment on function public.match_knowledge_chunks is
  'Cautare hibrida: distanta cosinus (scor primar) + plasa de siguranta full-text (p_query_text), cu filtre de izolare (embedding_key, limba, tip_document, categorie, audienta) aplicate inainte de scor.';

grant execute on function public.match_knowledge_chunks to authenticated;

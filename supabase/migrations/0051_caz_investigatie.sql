-- =============================================================================
-- 0051 — Cazul de investigatie: firul dintre banca si client
--
-- Pana acum comunicarea mergea intr-un singur sens sau pornea de la client:
-- `notificari` duce mesaje banca -> client, `cereri_suport` duce client -> banca.
-- Lipsea firul pe care il deschide BANCA si in care clientul raspunde — exact ce
-- trebuie cand un card a fost blocat si administratorul vrea sa afle daca omul
-- si-a facut singur platile sau i-a fost spart contul.
--
-- Blocarea NU e o stare a cazului. Ea traieste pe `conturi_bancare` si e aparata
-- de un trigger (0030). Un caz poate exista fara blocare, iar un cont poate fi
-- blocat fara caz; daca le-as fi topit intr-o singura axa, una din cele doua ar
-- fi devenit imposibila.
-- =============================================================================

create table if not exists public.caz_investigatie (
  id               uuid primary key default gen_random_uuid(),
  id_utilizator    uuid        not null references public.profiles (id) on delete cascade,
  id_administrator uuid        not null references public.profiles (id),

  stare            text        not null default 'nou',
  motiv_deschidere text        not null,

  -- Ce se vedea cand s-a deschis cazul. Inghetat: peste un an, pragurile
  -- detectiei pot fi altele, iar cine citeste dosarul trebuie sa vada pe ce s-a
  -- pornit, nu ce ar iesi azi.
  gravitate        integer,
  numar_semnalari  integer,

  -- Completat la inchidere. 'anaf' inseamna „predat conformitatii", nu
  -- „raportat": sesizarea catre o autoritate are temei legal si procedura, si nu
  -- se face dintr-un buton.
  rezultat         text,

  deschis_la       timestamptz not null default now(),
  inchis_la        timestamptz,

  constraint caz_stare_check check (stare in (
    'nou', 'in_analiza', 'asteptam_clientul', 'client_a_raspuns',
    'rezolvat', 'escalat', 'inchis'
  )),
  constraint caz_rezultat_check check (rezultat is null or rezultat in (
    'fara_masuri', 'deblocat', 'sucursala', 'anaf'
  )),
  constraint caz_motiv_check check (char_length(btrim(motiv_deschidere)) between 3 and 2000)
);

comment on table public.caz_investigatie is
  'Investigatia deschisa de banca pe contul unui client, cu firul de discutie in caz_mesaj.';
comment on column public.caz_investigatie.rezultat is
  'anaf = predat echipei de conformitate, nu raportat direct autoritatii.';

create index if not exists caz_utilizator_idx
  on public.caz_investigatie (id_utilizator, deschis_la desc);

-- Coada administratorului: cazurile nerezolvate, cel mai vechi primul. Cine
-- asteapta de trei zile trebuie sa fie deasupra celui deschis acum o ora.
create index if not exists caz_deschise_idx
  on public.caz_investigatie (deschis_la)
  where stare not in ('rezolvat', 'escalat', 'inchis');


-- Tranzactiile care au dus la deschiderea cazului. Tabela de legatura, nu o
-- coloana cu id-uri: un caz porneste de obicei de la mai multe plati.
create table if not exists public.caz_tranzactie (
  id_caz        uuid not null references public.caz_investigatie (id) on delete cascade,
  id_tranzactie uuid not null references public.tranzactii (id) on delete cascade,
  motiv         text,

  primary key (id_caz, id_tranzactie)
);


-- -----------------------------------------------------------------------------
-- Firul de discutie
--
-- Raspunsurile structurate ale clientului si analiza agentului NU primesc tabele
-- proprii: intra tot aici, cu `structura` in jsonb. Un fir cu trei tabele
-- paralele se desincronizeaza la prima schimbare.
-- -----------------------------------------------------------------------------

create table if not exists public.caz_mesaj (
  id       uuid primary key default gen_random_uuid(),
  id_caz   uuid        not null references public.caz_investigatie (id) on delete cascade,

  autor    text        not null,
  id_autor uuid        references public.profiles (id) on delete set null,
  text     text        not null,

  -- Raspunsul clientului, adus in campuri comparabile, sau analiza pentru
  -- administrator. Gol pentru mesajele obisnuite.
  structura jsonb      not null default '{}'::jsonb,

  -- Peste sase luni, la o contestatie, intrebarea „textul asta l-a scris un om
  -- sau un model, si l-a citit cineva inainte?" trebuie sa aiba raspuns in date,
  -- nu in amintiri.
  propus_de_agent boolean not null default false,
  editat_de_om    boolean not null default false,

  creat_la timestamptz not null default now(),

  constraint caz_mesaj_autor_check check (autor in ('banca', 'client', 'sistem')),
  constraint caz_mesaj_text_check check (char_length(btrim(text)) between 1 and 4000)
);

create index if not exists caz_mesaj_fir_idx
  on public.caz_mesaj (id_caz, creat_la);


-- -----------------------------------------------------------------------------
-- Cine vede ce
-- -----------------------------------------------------------------------------

alter table public.caz_investigatie enable row level security;
alter table public.caz_tranzactie   enable row level security;
alter table public.caz_mesaj        enable row level security;

drop policy if exists "caz propriu: select" on public.caz_investigatie;
create policy "caz propriu: select"
  on public.caz_investigatie for select to authenticated
  using (auth.uid() = id_utilizator or public.este_administrator());

drop policy if exists "caz tranzactii: select" on public.caz_tranzactie;
create policy "caz tranzactii: select"
  on public.caz_tranzactie for select to authenticated
  using (public.este_administrator());

drop policy if exists "caz mesaje: select" on public.caz_mesaj;
create policy "caz mesaje: select"
  on public.caz_mesaj for select to authenticated
  using (
    public.este_administrator()
    or exists (
      select 1 from public.caz_investigatie c
       where c.id = caz_mesaj.id_caz and c.id_utilizator = auth.uid()
    )
  );

-- Nicio politica de insert sau update pentru 'authenticated': tot ce se scrie
-- trece prin backend, cu service-role, dupa ce s-a verificat cine cere. Un
-- client nu trebuie sa poata adauga un mesaj „de la banca" in propriul dosar.


-- -----------------------------------------------------------------------------
-- Firul nu se rescrie
--
-- Aceeasi regula ca la notificari (0020): cine s-a razgandit adauga un mesaj
-- nou. Un istoric care se poate rescrie nu e istoric, iar dosarul asta poate
-- ajunge intr-o contestatie.
-- -----------------------------------------------------------------------------

create or replace function public.caz_mesaj_imutabil()
returns trigger
language plpgsql
security definer
set search_path to ''
as $$
begin
  raise exception 'CAZ_MESAJ_IMUTABIL'
    using detail = 'Mesajele dintr-un caz nu se modifica. Adauga unul nou.';
end;
$$;

drop trigger if exists caz_mesaj_fara_update on public.caz_mesaj;

create trigger caz_mesaj_fara_update
  before update on public.caz_mesaj
  for each row execute function public.caz_mesaj_imutabil();

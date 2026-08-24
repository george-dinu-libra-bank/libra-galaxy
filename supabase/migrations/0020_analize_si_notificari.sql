-- =============================================================================
-- 0020 — Analiza administratorului asupra unui cont, si notificarile clientului
--
-- STRICT ADITIVA. Nu modifica, nu sterge si nu altereaza nimic din ce exista:
-- niciun ALTER pe tabele existente, nicio constrangere schimbata, nicio functie
-- rescrisa. Doua tabele noi si politicile lor, atat.
--
-- Ce NU face, desi ar fi fost natural:
--
--   1. Nu extinde `acces_administrator.acces_actiune_check`. Tabela aceea
--      inregistreaza CINE A VAZUT ce, nu verdicte. O decizie cu observatie e
--      alt lucru si primeste tabela ei.
--
--   2. Nu adauga o garda in `public.core_banking`. Ar fi singurul loc unde
--      blocarea ar opri si transferurile pe IBAN, dar ar insemna rescrierea unei
--      functii existente. Consecinta, scrisa aici ca sa nu fie o surpriza:
--      blocarea opreste platile cu cardul (RPC-ul de plata verifica
--      `carduri.is_blocked`), dar NU opreste transferurile. Aplicatia verifica
--      inainte sa cheme functia, ceea ce acopera drumul normal, nu si pe cineva
--      care ar chema RPC-ul direct cu tokenul lui.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Analizele administratorului
--
-- Fiecare rand e o hotarare luata de un om asupra unui cont semnalat, cu ce a
-- vazut atunci. Se adauga, nu se modifica: un istoric care poate fi rescris nu
-- e un istoric. Daca administratorul se razgandeste, adauga o decizie noua.
-- -----------------------------------------------------------------------------

create table if not exists public.analize_cont (
  id               uuid primary key default gen_random_uuid(),
  id_utilizator    uuid        not null references public.profiles (id) on delete cascade,
  id_administrator uuid        not null references public.profiles (id),

  decizie          text        not null,
  observatie       text,

  -- Ce se vedea in momentul deciziei. Pastrat aici, nu recalculat: peste un an,
  -- pragurile detectorului pot fi altele, iar cine citeste istoricul trebuie sa
  -- vada pe ce s-a hotarat atunci, nu ce ar iesi azi.
  gravitate        integer,
  numar_semnalari  integer,
  zile_analizate   integer,

  -- Ce s-a intamplat efectiv cu contul in urma deciziei.
  carduri_blocate  integer     not null default 0,

  creat_la         timestamptz not null default now(),

  constraint analize_decizie_check check (decizie in ('acceptat', 'frauda', 'deblocat')),
  constraint analize_observatie_check check (observatie is null or char_length(observatie) <= 2000)
);

comment on table public.analize_cont is
  'Hotararile administratorului asupra conturilor semnalate. Se adauga, nu se modifica.';
comment on column public.analize_cont.decizie is
  'acceptat = semnalele au fost verificate si nu se confirma; frauda = se confirma si contul a fost blocat; deblocat = blocarea a fost ridicata.';
comment on column public.analize_cont.gravitate is
  'Gravitatea contului la momentul deciziei (1-100), inghetata deliberat.';

create index if not exists analize_cont_utilizator_idx
  on public.analize_cont (id_utilizator, creat_la desc);

alter table public.analize_cont enable row level security;

-- Clientul isi vede propriile analize: e vorba despre contul lui si despre o
-- masura luata asupra lui.
drop policy if exists "analize proprii: select" on public.analize_cont;
create policy "analize proprii: select"
  on public.analize_cont for select to authenticated
  using (auth.uid() = id_utilizator or public.este_administrator());

-- Scrierea merge prin backend, cu service-role, dupa ce rolul e verificat in
-- aplicatie. Nicio politica de insert pentru 'authenticated': un client nu-si
-- poate inventa o analiza favorabila.


-- -----------------------------------------------------------------------------
-- 2. Notificarile clientului
--
-- In aplicatie, nu pe email: raman in sistem, se pot verifica mai tarziu si nu
-- depind de un serviciu extern. Un om caruia i s-a blocat contul trebuie sa
-- afle de ce de la banca, nu de la un card refuzat la casa.
-- -----------------------------------------------------------------------------

create table if not exists public.notificari (
  id            uuid primary key default gen_random_uuid(),
  id_utilizator uuid        not null references public.profiles (id) on delete cascade,

  titlu         text        not null,
  mesaj         text        not null,
  tip           text        not null default 'info',

  citita_la     timestamptz,
  creat_la      timestamptz not null default now(),

  constraint notificari_tip_check check (tip in ('info', 'atentionare', 'blocare', 'deblocare')),
  constraint notificari_titlu_check check (char_length(btrim(titlu)) between 1 and 200),
  constraint notificari_mesaj_check check (char_length(btrim(mesaj)) between 1 and 4000)
);

comment on table public.notificari is
  'Mesaje de la banca pentru client, citite in aplicatie.';

create index if not exists notificari_utilizator_idx
  on public.notificari (id_utilizator, creat_la desc);

alter table public.notificari enable row level security;

drop policy if exists "notificari proprii: select" on public.notificari;
create policy "notificari proprii: select"
  on public.notificari for select to authenticated
  using (auth.uid() = id_utilizator or public.este_administrator());

-- Clientul poate doar sa marcheze ca a citit. Nu poate schimba textul: altfel
-- ar putea rescrie motivul pentru care i s-a blocat contul.
drop policy if exists "notificari proprii: marcheaza citita" on public.notificari;
create policy "notificari proprii: marcheaza citita"
  on public.notificari for update to authenticated
  using (auth.uid() = id_utilizator)
  with check (auth.uid() = id_utilizator);

drop trigger if exists notificari_pastreaza_textul on public.notificari;

create or replace function public.notificari_pastreaza_textul()
returns trigger
language plpgsql
security definer
set search_path to ''
as $$
begin
  -- Doar `citita_la` se poate schimba de catre client; restul raman cum au fost
  -- scrise. Verificarea sta in baza, nu doar in aplicatie, fiindca politica de
  -- update de mai sus nu poate limita si ce coloane sunt atinse.
  if new.id_utilizator is distinct from old.id_utilizator
     or new.titlu is distinct from old.titlu
     or new.mesaj is distinct from old.mesaj
     or new.tip is distinct from old.tip
     or new.creat_la is distinct from old.creat_la then
    raise exception 'NOTIFICARE_IMUTABILA'
      using detail = 'Doar citita_la poate fi modificata.';
  end if;
  return new;
end;
$$;

create trigger notificari_pastreaza_textul
  before update on public.notificari
  for each row execute function public.notificari_pastreaza_textul();

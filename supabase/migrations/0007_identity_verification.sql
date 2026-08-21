-- =============================================================================
-- Libra — verificare identitate la inregistrare (buletin OCR + selfie DeepFace)
--
-- Inlocuieste introducerea manuala a CNP-ului: userul incarca o poza a
-- buletinului (CNP-ul se citeste automat prin OCR in serviciul FastAPI) si un
-- selfie facut pe loc; DeepFace (ArcFace) compara fetele si scrie rezultatul
-- aici. Scorurile mici nu blocheaza inregistrarea — contul ramane
-- 'pending_review' pana la o revizuire manuala (admin panel viitor).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Status rezumat pe profil (citit des; sursa de adevar e identity_verifications)
-- -----------------------------------------------------------------------------
alter table public.profiles
  add column if not exists verification_status text not null default 'pending';

alter table public.profiles drop constraint if exists profiles_verification_status_check;
alter table public.profiles
  add constraint profiles_verification_status_check
  check (verification_status in ('pending', 'verified', 'pending_review', 'rejected'));

comment on column public.profiles.verification_status is
  'Rezumat al ultimei verificari de identitate; sursa de adevar e identity_verifications.';

-- -----------------------------------------------------------------------------
-- 2. Istoricul incercarilor de verificare (audit trail)
-- -----------------------------------------------------------------------------
create table if not exists public.identity_verifications (
  id                  uuid primary key default gen_random_uuid(),
  id_user             uuid not null references public.profiles (id) on delete cascade,
  buletin_image_path  text not null,
  selfie_image_path   text not null,
  extracted_cnp       text,
  similarity_score    numeric(6,5),
  threshold_folosit   numeric(6,5),
  status              text not null default 'pending_review',

  -- Rezervate pentru admin panel-ul viitor; necompletate de aplicatie inca.
  reviewed_by         uuid references public.profiles (id),
  reviewed_at         timestamptz,
  notes               text,

  creat_la            timestamptz not null default now(),

  constraint identity_verifications_status_check
    check (status in ('verified', 'pending_review', 'rejected'))
);

comment on table public.identity_verifications is
  'Istoric al incercarilor de verificare identitate (OCR + DeepFace). O incercare pe inregistrare/reincercare; profiles.verification_status reflecta ultima.';
comment on column public.identity_verifications.reviewed_by is
  'TODO(admin-panel): id-ul adminului care a revizuit manual cazul cu scor mic. Nescris de aplicatie inca.';
comment on column public.identity_verifications.notes is
  'TODO(admin-panel): note lasate de admin la revizuirea manuala.';

create index if not exists identity_verifications_id_user_idx
  on public.identity_verifications (id_user, creat_la desc);

-- -----------------------------------------------------------------------------
-- 3. Sincronizare profiles.verification_status din ultima verificare
-- -----------------------------------------------------------------------------
create or replace function public.sync_verification_status()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.profiles
     set verification_status = new.status,
         modificat_la = now()
   where id = new.id_user;

  return new;
end;
$$;

drop trigger if exists identity_verifications_after_insert on public.identity_verifications;
create trigger identity_verifications_after_insert
  after insert on public.identity_verifications
  for each row
  execute function public.sync_verification_status();

-- -----------------------------------------------------------------------------
-- 4. RLS — userul isi vede propriile incercari; scrierea e doar service_role
--    (FastAPI foloseste service-role key, ca la carduri/tranzactii)
-- -----------------------------------------------------------------------------
alter table public.identity_verifications enable row level security;

drop policy if exists "verificari proprii: select" on public.identity_verifications;
create policy "verificari proprii: select"
  on public.identity_verifications
  for select
  to authenticated
  using (auth.uid() = id_user);

-- Nicio politica de insert/update pentru 'authenticated': randurile se scriu
-- doar din FastAPI (service_role), ca sold_curent la carduri.
-- TODO(admin-panel): politica separata pentru rol 'admin' cu select/update pe toate randurile.

grant select on public.identity_verifications to authenticated;

-- -----------------------------------------------------------------------------
-- 5. Storage: bucket-uri private pentru buletin si selfie (spre deosebire de
--    'avatare', acestea nu sunt publice — sunt documente de identitate)
-- -----------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('buletine', 'buletine', false)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('selfie-uri', 'selfie-uri', false)
on conflict (id) do nothing;

-- Userul poate incarca/vedea doar in propriul folder (user.id/...), la fel ca
-- la 'avatare'. Scrierile din fluxul de inregistrare folosesc oricum
-- service_role (vezi identitate.ts), dar politicile raman ca plasa de
-- siguranta pentru orice acces facut cu sesiunea userului.
drop policy if exists "buletine: user isi incarca poza proprie" on storage.objects;
create policy "buletine: user isi incarca poza proprie"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'buletine' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "buletine: user isi vede poza proprie" on storage.objects;
create policy "buletine: user isi vede poza proprie"
  on storage.objects for select to authenticated
  using (bucket_id = 'buletine' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "selfie: user isi incarca poza proprie" on storage.objects;
create policy "selfie: user isi incarca poza proprie"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'selfie-uri' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "selfie: user isi vede poza proprie" on storage.objects;
create policy "selfie: user isi vede poza proprie"
  on storage.objects for select to authenticated
  using (bucket_id = 'selfie-uri' and (storage.foldername(name))[1] = auth.uid()::text);

-- TODO(admin-panel, viitor): politica de select pentru rol admin pe ambele bucket-uri.

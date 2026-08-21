-- =============================================================================
-- Libra — RLS pentru revizuirea de admin a verificarilor de identitate
--
-- Backend-ul foloseste service-role la /api/identity/admin/* (ocoleste RLS),
-- iar bariera reala e cere_administrator() din Python. Politicile de aici sunt
-- a doua bariera, pentru orice acces facut cu sesiunea unui admin — nu pentru
-- fluxul normal al aplicatiei.
--
-- Aditiva: nu schimba public.este_administrator() (ramane cea din 0008, pe
-- profiles.rol) — doar adauga politici si trigger-e noi peste ea.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Ce vede/schimba un administrator pe verificari si profiluri
-- -----------------------------------------------------------------------------
drop policy if exists "admin: vede toate verificarile" on public.identity_verifications;
create policy "admin: vede toate verificarile"
  on public.identity_verifications
  for select
  to authenticated
  using (public.este_administrator());

-- Update-ul e ingustat la coloanele deciziei prin trigger-ul de la punctul 2:
-- politica singura n-ar impiedica un admin sa rescrie scorul sau calea pozei.
drop policy if exists "admin: decide asupra verificarilor" on public.identity_verifications;
create policy "admin: decide asupra verificarilor"
  on public.identity_verifications
  for update
  to authenticated
  using (public.este_administrator())
  with check (public.este_administrator());

drop policy if exists "admin: vede profilurile" on public.profiles;
create policy "admin: vede profilurile"
  on public.profiles
  for select
  to authenticated
  using (public.este_administrator());

grant update on public.identity_verifications to authenticated;

-- -----------------------------------------------------------------------------
-- 2. Ce poate schimba un administrator intr-un caz
--
-- Doar decizia: status, reviewed_by, reviewed_at, notes. Dovezile pe care se
-- ia decizia — poze, CNP citit, scor, prag — raman cum le-a scris serviciul.
-- Altfel un raport de revizuire nu ar mai putea fi verificat de nimeni.
-- -----------------------------------------------------------------------------
create or replace function public.identity_verifications_protejeaza_dovezile()
returns trigger
language plpgsql
set search_path = ''
as $functie$
begin
  new.id                 := old.id;
  new.id_user            := old.id_user;
  new.buletin_image_path := old.buletin_image_path;
  new.selfie_image_path  := old.selfie_image_path;
  new.extracted_cnp      := old.extracted_cnp;
  new.similarity_score   := old.similarity_score;
  new.threshold_folosit  := old.threshold_folosit;
  new.creat_la           := old.creat_la;

  return new;
end;
$functie$;

drop trigger if exists identity_verifications_before_update on public.identity_verifications;
create trigger identity_verifications_before_update
  before update on public.identity_verifications
  for each row
  execute function public.identity_verifications_protejeaza_dovezile();

-- Decizia manuala trebuie sa se reflecte in profil, la fel ca cea automata.
-- Trigger-ul din 0007 prinde doar INSERT.
create or replace function public.sync_verification_status_update()
returns trigger
language plpgsql
security definer
set search_path = ''
as $functie$
begin
  if new.status is distinct from old.status then
    update public.profiles
       set verification_status = new.status,
           modificat_la = now()
     where id = new.id_user;
  end if;

  return new;
end;
$functie$;

drop trigger if exists identity_verifications_after_update on public.identity_verifications;
create trigger identity_verifications_after_update
  after update on public.identity_verifications
  for each row
  execute function public.sync_verification_status_update();

-- -----------------------------------------------------------------------------
-- 3. Pozele
--
-- Bucket-urile raman private. Administratorul primeste drept de citire, ca sa
-- se poata genera un URL semnat cu durata scurta; nimic nu devine public.
-- Politicile utilizatorilor pe propriile poze raman neatinse.
-- -----------------------------------------------------------------------------
drop policy if exists "buletine: adminul vede toate pozele" on storage.objects;
create policy "buletine: adminul vede toate pozele"
  on storage.objects for select to authenticated
  using (bucket_id = 'buletine' and public.este_administrator());

drop policy if exists "selfie: adminul vede toate pozele" on storage.objects;
create policy "selfie: adminul vede toate pozele"
  on storage.objects for select to authenticated
  using (bucket_id = 'selfie-uri' and public.este_administrator());

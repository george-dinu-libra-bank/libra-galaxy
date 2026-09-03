-- =============================================================================
-- 0055 — inca opt modele de fundal pentru grupuri
--
-- 0054 a livrat opt fundaluri, toate desenate din gradiente CSS: de aceea erau
-- toate geometrice (buline, grila, romburi, diagonale, valuri, stropi). Un
-- gradient nu poate desena o inimioara sau un nor, asa ca lipseau exact
-- modelele pe care un grup de familie sau de prieteni si le-ar alege primele.
--
-- Se adauga opt:
--
--   geometrice, tot din gradiente — 'zigzag', 'confetti', 'cercuri'
--   cu forma proprie             — 'inimioare', 'nori', 'stele', 'frunze',
--                                  'triunghiuri'
--
-- Cele cu forma proprie isi iau silueta dintr-un SVG, folosit insa ca MASCA, nu
-- ca imagine (`.fundal-grup-*::before` din globals.css). Diferenta conteaza:
-- intr-un `background-image` culoarea ar fi fost scrisa in interiorul SVG-ului,
-- deci modelul n-ar mai fi urmat accentul grupului si ar fi trebuit livrat in
-- opt variante. Ca masca, forma vine din SVG iar culoarea din rampa — la fel ca
-- la modelele din gradiente. Baza tot nu stie nimic despre asta: pastreaza doar
-- numele.
--
-- De ce o migratie noua si nu o editare a lui 0054: 0054 e deja aplicata.
-- Migratiile sunt strict aditive (REGULI.md §3).
--
-- Coloana, defaultul si garda de apartenenta raman cele din 0054. Se schimba
-- doar cele doua liste de valori permise — constraint-ul si cea din functie —
-- care trebuie sa ramana identice intre ele.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Constraint-ul
-- -----------------------------------------------------------------------------

alter table public.groups
  drop constraint if exists groups_fundal_check;

alter table public.groups
  add constraint groups_fundal_check
  check (fundal in (
    'implicit', 'simplu', 'buline', 'grila',
    'romburi', 'diagonale', 'valuri', 'stropi',
    'zigzag', 'confetti', 'cercuri',
    'inimioare', 'nori', 'stele', 'frunze', 'triunghiuri'
  ));


-- -----------------------------------------------------------------------------
-- 2. Functia, cu lista noua
-- -----------------------------------------------------------------------------

/**
 * Identica cu cea din 0054, in afara listei de fundaluri acceptate.
 *
 * Se rescrie intreaga functie, nu doar bucata schimbata: `create or replace`
 * inlocuieste corpul cu totul, deci o versiune partiala ar sterge restul
 * verificarilor. Vezi 0054_tema_grup.sql pentru de ce garda e apartenenta la
 * grup si nu `id_creator`.
 */
create or replace function public.seteaza_tema_grup(
  p_id_group bigint,
  p_tema text,
  p_emblema text,
  p_fundal text
)
 returns jsonb
 language plpgsql
 security definer
 set search_path to ''
as $function$
declare
  v_user uuid := auth.uid();
begin
  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat.';
  end if;

  if not exists (select 1 from public.groups g where g.id = p_id_group) then
    raise exception 'GRUP_INEXISTENT'
      using detail = 'Nu exista acest grup.';
  end if;

  -- Apartenenta, nu `id_creator`: tema e a grupului, o schimba oricine e in el.
  if not exists (
    select 1
      from public.groups_participants p
     where p.id_group = p_id_group
       and p.id_user = v_user
  ) then
    raise exception 'NU_ESTI_MEMBRU'
      using detail = 'Nu faci parte din acest grup.';
  end if;

  if p_tema is null or p_tema not in (
    'implicit', 'smarald', 'turcoaz', 'ametist',
    'zmeura', 'chihlimbar', 'scortisoara', 'grafit'
  ) then
    raise exception 'TEMA_INVALIDA'
      using detail = 'Culoarea trimisa nu e una dintre presetarile cunoscute.';
  end if;

  if p_emblema is null or p_emblema not in (
    'users', 'home', 'plane', 'party',
    'briefcase', 'heart', 'graduation', 'basket'
  ) then
    raise exception 'EMBLEMA_INVALIDA'
      using detail = 'Emblema trimisa nu e una dintre cele cunoscute.';
  end if;

  if p_fundal is null or p_fundal not in (
    'implicit', 'simplu', 'buline', 'grila',
    'romburi', 'diagonale', 'valuri', 'stropi',
    'zigzag', 'confetti', 'cercuri',
    'inimioare', 'nori', 'stele', 'frunze', 'triunghiuri'
  ) then
    raise exception 'FUNDAL_INVALID'
      using detail = 'Fundalul trimis nu e unul dintre modelele cunoscute.';
  end if;

  update public.groups
     set tema = p_tema,
         emblema = p_emblema,
         fundal = p_fundal
   where id = p_id_group;

  return jsonb_build_object(
    'id_group', p_id_group,
    'tema', p_tema,
    'emblema', p_emblema,
    'fundal', p_fundal
  );
end;
$function$;

-- `create or replace` pastreaza drepturile existente, dar le repetam ca migratia
-- sa fie completa daca cineva o ruleaza pe o baza pornita de la zero.
revoke all on function public.seteaza_tema_grup(bigint, text, text, text) from public;
grant execute on function public.seteaza_tema_grup(bigint, text, text, text) to authenticated;

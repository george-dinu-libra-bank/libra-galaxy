-- =============================================================================
-- 0018 — o singura sursa de adevar pentru "cine e administrator"
--
-- Pana acum aceeasi intrebare primea trei raspunsuri diferite:
--
--   frontend/src/lib/admin.ts        user_roles.role = 'admin'
--   backend .../dependencies.py      profiles.rol    = 'administrator'
--   public.este_administrator()      user_roles.role = 'administrator'   (0009)
--
-- In baza reala, `user_roles.role` contine 'admin' pentru toate randurile, si
-- niciodata 'administrator'. Consecintele, masurate inainte de a scrie:
--
--   * `este_administrator()` intorcea false pentru TOATA lumea, deci toate
--     politicile RLS din 0009 care depind de ea blocau si administratorii.
--   * Cine avea rand in user_roles intra in interfata de admin (frontendul il
--     lasa) dar primea 403 la fiecare apel de backend, care se uita in alta
--     tabela.
--
-- Decizia: sursa de adevar e `public.user_roles`, iar valoarea e 'admin'.
-- Codul din aplicatie a fost aliniat in acelasi commit (ROL_ADMIN, in ambele
-- limbaje). `profiles.rol` ramane in schema, dar nu mai decide nimic — nicio
-- linie de cod nu-l mai citeste.
--
-- Nota despre 0009: comentariul de acolo sustine ca `profiles.rol` nu exista in
-- baza. Exista, si contine un 'administrator' ramas de dinainte. Nu il stergem
-- aici: o coloana nefolosita nu strica nimic, iar stersul ei e o decizie
-- separata, cu date in ea.
-- =============================================================================

create or replace function public.este_administrator()
returns boolean
language sql
stable
security definer
set search_path to ''
as $$
  select exists (
    select 1
      from public.user_roles r
     where r.user_id = auth.uid()
       and r.role = 'admin'
  );
$$;

comment on function public.este_administrator() is
  'True daca utilizatorul din sesiune are rol ''admin'' in public.user_roles. '
  'Valoarea trebuie sa ramana identica cu ROL_ADMIN din backend/app/api/dependencies.py '
  'si din frontend/src/lib/admin.ts.';

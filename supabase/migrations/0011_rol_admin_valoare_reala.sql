-- =============================================================================
-- Libra — `este_administrator()` accepta valoarea reala a rolului
--
-- 0009 a scris functia cautand `role = 'administrator'`. Randurile care exista
-- de fapt in public.user_roles au insa `role = 'admin'` — au fost puse din
-- consola, inainte ca aplicatia sa aiba vreo parere despre cum se numeste rolul.
--
-- Rezultatul: functia intorcea `false` pentru administratori reali, deci toate
-- politicile si toate rutele de admin erau inchise pentru toata lumea.
--
-- Se accepta ambele valori in loc sa se rescrie datele. Un `update` pe user_roles
-- ar fi schimbat randuri pe care le administreaza altcineva din consola, iar
-- migrarea trebuie sa ramana aditiva: adauga o valoare acceptata, nu modifica
-- date existente.
-- =============================================================================

create or replace function public.este_administrator()
returns boolean
language sql
stable
security definer
set search_path = ''
as $functie$
  select exists (
    select 1
      from public.user_roles r
     where r.user_id = auth.uid()
       and r.role in ('admin', 'administrator')
  );
$functie$;

revoke all on function public.este_administrator() from public;
grant execute on function public.este_administrator() to authenticated;

-- =============================================================================
-- 0038 — Stergerea efectiva a clientului, cu poarta pe solduri
--
-- Regula bancii: nu se sterge un client care mai are bani la noi. Poarta sta
-- AICI, in baza, nu doar in interfata de admin: un buton dezactivat e o
-- sugestie, o exceptie din functie e o regula. Aceeasi disciplina ca la
-- creeaza_plata, unde verificarile stau in RPC, nu in formular.
--
-- Conturile blocate administrativ nu se ignora: daca banca a inghetat un cont,
-- decizia de stergere trebuie luata dupa ce cineva se uita de ce l-a inghetat.
--
-- Stergerea randului din `profiles` duce mai departe prin cascada la conturi si
-- carduri; tranzactiile raman, cu referintele golite — asta a reparat 0034.
-- Utilizatorul din schema `auth` se sterge separat, din backend: SQL-ul nostru
-- n-are ce cauta acolo.
-- =============================================================================

create or replace function public.sterge_client(p_id_cerere uuid, p_id_admin uuid)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_cerere    public.cereri_stergere_cont%rowtype;
  v_cu_sold   integer;
  v_blocate   integer;
  v_credite   integer;
  v_id_user   uuid;
begin
  select c.* into v_cerere
  from public.cereri_stergere_cont c
  where c.id = p_id_cerere
  for update;

  if not found then
    raise exception 'CERERE_INEXISTENTA' using detail = 'Cererea nu exista.';
  end if;

  if v_cerere.status <> 'aprobata' then
    raise exception 'CERERE_NEAPROBATA'
      using detail = 'Se poate sterge doar dupa ce cererea a fost aprobata.';
  end if;

  v_id_user := v_cerere.id_utilizator;

  select count(*) into v_cu_sold
  from public.conturi_bancare c
  where c.id_user = v_id_user and c.sold <> 0;

  if v_cu_sold > 0 then
    raise exception 'CONTURI_CU_SOLD'
      using detail = 'Clientul mai are ' || v_cu_sold ||
                     ' cont(uri) cu sold diferit de zero. Consolideaza si goleste-le intai.';
  end if;

  select count(*) into v_blocate
  from public.conturi_bancare c
  where c.id_user = v_id_user and c.blocat_administrativ;

  if v_blocate > 0 then
    raise exception 'CONTURI_BLOCATE'
      using detail = 'Clientul are conturi blocate administrativ. Lamureste blocarea inainte de stergere.';
  end if;

  select count(*) into v_credite
  from public.credite c
  where c.id_user = v_id_user and c.status in ('activ', 'restant');

  if v_credite > 0 then
    raise exception 'CREDITE_IN_DERULARE'
      using detail = 'Clientul are credite in derulare.';
  end if;

  delete from public.profiles p where p.id = v_id_user;

  return jsonb_build_object('id_utilizator', v_id_user, 'sters_la', now());
end;
$$;

comment on function public.sterge_client(uuid, uuid) is
  'Sterge clientul dupa o cerere aprobata. Refuza daca mai are solduri nenule, '
  'conturi blocate sau credite in derulare.';

revoke all on function public.sterge_client(uuid, uuid) from public, anon, authenticated;
grant execute on function public.sterge_client(uuid, uuid) to service_role;

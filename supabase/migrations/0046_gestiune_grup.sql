-- =============================================================================
-- 0046 — stergerea unui grup si eliminarea unui membru, de catre creator
--
-- Pana acum un grup nu putea fi sters (doar parasit, unul cate unul — vezi
-- politica "participanti: iesire din grup", 0000_instantaneu...sql) si niciun
-- membru nu putea scoate pe altcineva din grup. Aici se adauga doua actiuni,
-- ambele rezervate creatorului (`groups.id_creator`):
--
--   - sterge_grup: sterge grupul intreg (cascada curata participantii,
--     mesajele si invitatiile — toate au deja ON DELETE CASCADE pe id_group).
--     Blocat cat timp mai e sold in grup, la fel cum inchiderea unui cont
--     bancar e blocata cat timp mai are bani (0037_stergere_cont_decizie.sql):
--     banii trebuie scosi intai (plata din grup catre un cont), nu dispar
--     odata cu grupul.
--   - elimina_membru_grup: scoate un ALT membru din grup. Nu inlocuieste
--     iesirea voluntara (participanti: iesire din grup ramane calea pentru a
--     pleca singur) — aici creatorul alege pentru altcineva, deci merge prin
--     RPC, nu prin politica de DELETE de pe groups_participants.
-- =============================================================================

CREATE OR REPLACE FUNCTION public.sterge_grup(p_id_group bigint)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_user uuid := auth.uid();
  v_grup public.groups%rowtype;
begin
  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat.';
  end if;

  select * into v_grup from public.groups where id = p_id_group;

  if not found then
    raise exception 'GRUP_INEXISTENT'
      using detail = 'Nu exista acest grup.';
  end if;

  if v_grup.id_creator <> v_user then
    raise exception 'NU_ESTI_CREATORUL'
      using detail = 'Doar creatorul grupului il poate sterge.';
  end if;

  if v_grup.sold <> 0 then
    raise exception 'SOLD_NEZERO'
      using detail = 'Golește soldul grupului înainte de a-l șterge.';
  end if;

  delete from public.groups where id = p_id_group;

  return jsonb_build_object('id', p_id_group);
end;
$function$;


CREATE OR REPLACE FUNCTION public.elimina_membru_grup(p_id_group bigint, p_id_membru uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_user       uuid := auth.uid();
  v_id_creator uuid;
begin
  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat.';
  end if;

  select id_creator into v_id_creator from public.groups where id = p_id_group;

  if v_id_creator is null then
    raise exception 'GRUP_INEXISTENT'
      using detail = 'Nu exista acest grup.';
  end if;

  if v_id_creator <> v_user then
    raise exception 'NU_ESTI_CREATORUL'
      using detail = 'Doar creatorul grupului poate elimina membri.';
  end if;

  if p_id_membru = v_user then
    raise exception 'NU_TE_POTI_ELIMINA'
      using detail = 'Folosește „Ieși din grup" ca să pleci singur.';
  end if;

  delete from public.groups_participants
   where id_group = p_id_group and id_user = p_id_membru;

  if not found then
    raise exception 'NU_ESTE_MEMBRU'
      using detail = 'Persoana nu face parte din grup.';
  end if;

  return jsonb_build_object('id_group', p_id_group, 'id_membru', p_id_membru);
end;
$function$;

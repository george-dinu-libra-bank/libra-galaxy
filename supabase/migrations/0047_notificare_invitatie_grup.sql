-- =============================================================================
-- 0047 — cel invitat intr-un grup primeste o notificare
--
-- invita_in_grup (0044_invitatii_grup.sql) scria doar randul in invitatii_grup;
-- persoana invitata n-avea cum sa afle decat deschizand singura pagina
-- Grupuri. Aici se adauga un rand in public.notificari (0020_analize_si_notificari.sql),
-- vazut deja in clopotelul de notificari existent — fara ecran nou.
--
-- `notificari.tip` accepta strict 'info' | 'atentionare' | 'blocare' | 'deblocare'
-- (vezi 0042_notificari_tip_valid.sql — nu se largeste constrangerea, se
-- traduce in vocabularul existent): o invitatie e 'info'.
--
-- Restul corpului functiei e identic cu 0044_invitatii_grup.sql.
-- =============================================================================

CREATE OR REPLACE FUNCTION public.invita_in_grup(p_id_group bigint, p_id_invitat uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_user           uuid := auth.uid();
  v_invitatie      public.invitatii_grup%rowtype;
  v_nume_grup      text;
  v_nume_invitator text;
begin
  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat ca sa inviti pe cineva.';
  end if;

  if not public.este_membru_grup(p_id_group) then
    raise exception 'NU_ESTI_MEMBRU'
      using detail = 'Nu faci parte din acest grup.';
  end if;

  if p_id_invitat = v_user then
    raise exception 'NU_TE_POTI_INVITA'
      using detail = 'Nu te poti invita singur.';
  end if;

  if exists (
    select 1 from public.groups_participants gp
     where gp.id_group = p_id_group and gp.id_user = p_id_invitat
  ) then
    raise exception 'DEJA_MEMBRU'
      using detail = 'Persoana face deja parte din grup.';
  end if;

  insert into public.invitatii_grup (id_group, id_invitat, id_invitator)
  values (p_id_group, p_id_invitat, v_user)
  on conflict (id_group, id_invitat) where status = 'in_asteptare' do nothing
  returning * into v_invitatie;

  if not found then
    raise exception 'DEJA_INVITAT'
      using detail = 'Exista deja o invitatie in asteptare pentru aceasta persoana.';
  end if;

  select g.nume into v_nume_grup      from public.groups   g where g.id = p_id_group;
  select p.nume into v_nume_invitator from public.profiles p where p.id = v_user;

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (
    p_id_invitat,
    'Invitație în grup',
    format(
      '%s te-a invitat în grupul „%s”. O găsești în Grupuri, la invitațiile primite.',
      coalesce(v_nume_invitator, 'Un utilizator Galaxy Bank'),
      v_nume_grup
    ),
    'info'
  );

  return jsonb_build_object(
    'id',         v_invitatie.id,
    'id_group',   v_invitatie.id_group,
    'id_invitat', v_invitatie.id_invitat
  );
end;
$function$;

-- =============================================================================
-- 0044 — invitatii de grup, catre persoane reale din tranzactiile tale
--
-- Azi singura cale de a intra intr-un grup e prin cod de acces, auto-servit
-- (intra_in_grup, insereaza mereu auth.uid() — niciodata un user_id ales de
-- altcineva). Aici se adauga o a doua cale: un membru al grupului invita o
-- CONTRAPARTE REALA (cineva cu cont Galaxy Bank, gasit din tranzactiile
-- proprii — vezi lib/data/tranzactii.ts::obtineContrapartiRecente, nicio
-- interogare noua acolo), iar acela primeste o invitatie pe care o accepta
-- sau o refuza singur. Nimeni nu e adaugat fara propriul gest — acelasi
-- model de securitate ca la codul de acces, doar ca gestul e "accepta"
-- in loc de "introdu codul".
-- =============================================================================

create table if not exists public.invitatii_grup (
  id           bigint generated always as identity primary key,
  id_group     bigint      not null references public.groups (id) on delete cascade,
  id_invitat   uuid        not null references public.profiles (id) on delete cascade,
  id_invitator uuid        not null references public.profiles (id) on delete cascade,
  status       text        not null default 'in_asteptare',
  creat_la     timestamptz not null default now(),
  decis_la     timestamptz,

  constraint invitatii_grup_status_check check (status in ('in_asteptare', 'acceptata', 'respinsa'))
);

comment on table public.invitatii_grup is
  'Invitatii nominale intr-un grup, pe langa codul de acces existent. O persoana e adaugata in groups_participants doar dupa ce ACCEPTA singura, prin raspunde_la_invitatie_grup — niciodata direct de cine invita.';

-- O singura invitatie ACTIVA per persoana per grup — dar o poti reinvita dupa
-- un refuz (indexul e partial, nu o constrangere unica pe toata tabela).
create unique index if not exists invitatii_grup_pendinte_unice
  on public.invitatii_grup (id_group, id_invitat)
  where status = 'in_asteptare';

create index if not exists invitatii_grup_invitat_idx on public.invitatii_grup (id_invitat, status);

-- -----------------------------------------------------------------------------
-- RLS — acelasi tipar ca groups/groups_participants (0000_instantaneu...sql):
-- nicio politica de insert/update pentru authenticated, totul trece prin
-- functiile SECURITY DEFINER de mai jos.
-- -----------------------------------------------------------------------------
alter table public.invitatii_grup enable row level security;

drop policy if exists "invitatii: select proprii" on public.invitatii_grup;
create policy "invitatii: select proprii"
  on public.invitatii_grup
  for select
  to authenticated
  using (auth.uid() in (id_invitat, id_invitator));

grant select on public.invitatii_grup to authenticated;


-- -----------------------------------------------------------------------------
-- invita_in_grup — chemat de un membru al grupului, pentru o contraparte reala
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.invita_in_grup(p_id_group bigint, p_id_invitat uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_user      uuid := auth.uid();
  v_invitatie public.invitatii_grup%rowtype;
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

  return jsonb_build_object(
    'id',         v_invitatie.id,
    'id_group',   v_invitatie.id_group,
    'id_invitat', v_invitatie.id_invitat
  );
end;
$function$;


-- -----------------------------------------------------------------------------
-- raspunde_la_invitatie_grup — doar cel invitat poate raspunde la propria
-- invitatie; acceptarea respecta acelasi plafon de 30 de grupuri ca
-- intra_in_grup.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.raspunde_la_invitatie_grup(p_id_invitatie bigint, p_accepta boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_max_grupuri constant integer := 30;
  v_user        uuid := auth.uid();
  v_invitatie   public.invitatii_grup%rowtype;
  v_cate        integer;
begin
  if v_user is null then
    raise exception 'NEAUTENTIFICAT'
      using detail = 'Trebuie sa fii autentificat.';
  end if;

  select * into v_invitatie
    from public.invitatii_grup
   where id = p_id_invitatie and id_invitat = v_user;

  if not found then
    raise exception 'INVITATIE_INEXISTENTA'
      using detail = 'Nu exista aceasta invitatie.';
  end if;

  if v_invitatie.status <> 'in_asteptare' then
    raise exception 'INVITATIE_DECISA'
      using detail = 'Ai raspuns deja la aceasta invitatie.';
  end if;

  if p_accepta then
    -- Reintrarea (daca ai iesit intre timp si esti reinvitat) nu trebuie sa
    -- pice in plafon — acelasi tratament ca in intra_in_grup.
    if not public.este_membru_grup(v_invitatie.id_group) then
      select count(*) into v_cate
        from public.groups_participants gp
       where gp.id_user = v_user;

      if v_cate >= v_max_grupuri then
        raise exception 'PREA_MULTE_GRUPURI'
          using detail = format('Poti face parte din cel mult %s grupuri.', v_max_grupuri);
      end if;

      insert into public.groups_participants (id_user, id_group)
      values (v_user, v_invitatie.id_group)
      on conflict (id_group, id_user) do nothing;
    end if;

    update public.invitatii_grup set status = 'acceptata', decis_la = now() where id = p_id_invitatie;
  else
    update public.invitatii_grup set status = 'respinsa', decis_la = now() where id = p_id_invitatie;
  end if;

  return jsonb_build_object('id', p_id_invitatie, 'accepta', p_accepta);
end;
$function$;


-- -----------------------------------------------------------------------------
-- invitatiile_mele — invitatiile primite, in asteptare, cu numele grupului si
-- al celui care a invitat. SECURITY DEFINER e necesar aici la fel ca la
-- grup_dupa_token: cel invitat inca nu e membru, deci politica normala de pe
-- `groups` (doar membrii vad) l-ar opri sa vada numele grupului la care e
-- invitat.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.invitatiile_mele()
 RETURNS TABLE(id bigint, id_group bigint, nume_grup text, nume_invitator text, creat_la timestamptz)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select ig.id, ig.id_group, g.nume, p.nume, ig.creat_la
    from public.invitatii_grup ig
    join public.groups g on g.id = ig.id_group
    join public.profiles p on p.id = ig.id_invitator
   where ig.id_invitat = auth.uid()
     and ig.status = 'in_asteptare'
   order by ig.creat_la desc;
$function$;

-- =============================================================================
-- 0052 — Redeschiderea contului deblocheaza si cardurile
--
-- RENUMEROTATA din 0051: intre timp 0051 a fost ocupat pe origin/main de
-- `0051_caz_investigatie.sql`. Continutul e neschimbat, doar numarul (REGULI.md #3).
--
-- Inchiderea (0042, mostenit din 0040) pune pe carduri DOUA lucruri:
--
--   update public.carduri set inchis_la = now(), is_blocked = true ...
--
-- `inchis_la` e al bancii, dar `is_blocked` e steagul CLIENTULUI (0032: banca isi
-- are `blocat_administrativ`, separat). `redeschide_cont` curata doar `inchis_la`,
-- asa ca dupa o redeschidere contul mergea, iar cardurile ramaneau blocate — cu un
-- steag pe care panoul de admin nici nu-l poate atinge. Clientul primea inapoi un
-- cont cu carduri moarte si nimeni nu avea de unde sa le invie.
--
-- Compromis asumat: un card pe care clientul il blocase SINGUR inainte de inchidere
-- se redeschide odata cu contul. E ales in cunostinta de cauza — sa retinem ce era
-- blocat inainte ar cere inca o coloana, iar un card blocat din greseala se blocheaza
-- la loc dintr-o apasare, pe cand unul blocat pentru totdeauna n-are iesire.
--
-- Restul functiei e neschimbat fata de 0040: aceeasi garda `CONT_NEINCHIS`, aceeasi
-- notificare, acelasi `anunta_utilizator`.
-- =============================================================================

create or replace function public.redeschide_cont(
  p_id_cont  uuid,
  p_id_admin uuid
)
returns public.conturi_bancare
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_cont public.conturi_bancare%rowtype;
begin
  update public.conturi_bancare c
     set inchis_la = null, modificat_la = now()
   where c.id = p_id_cont and c.inchis_la is not null
  returning * into v_cont;

  if not found then
    raise exception 'CONT_NEINCHIS'
      using detail = 'Contul nu exista sau nu e inchis.';
  end if;

  -- Se ridica si `is_blocked`, dar NUMAI pe cardurile pe care chiar inchiderea
  -- le-a inchis (`inchis_la is not null`). Un card inchis mai demult, din alt
  -- motiv, nu are ce cauta aici.
  update public.carduri
     set inchis_la = null, is_blocked = false, modificat_la = now()
   where id_cont = p_id_cont and inchis_la is not null;

  insert into public.notificari (id_utilizator, titlu, mesaj, tip)
  values (
    v_cont.id_user, 'Contul a fost redeschis',
    'Contul "' || v_cont.nume || '" a fost redeschis. Banii mutati la inchidere nu se ' ||
    'intorc automat — ii poti transfera inapoi cand vrei.',
    'info'
  );

  perform public.anunta_utilizator(
    v_cont.id_user, 'notificare',
    jsonb_build_object('id_cont', v_cont.id, 'status', 'redeschis')
  );

  return v_cont;
end;
$$;

revoke all on function public.redeschide_cont(uuid, uuid) from public, anon, authenticated;
grant execute on function public.redeschide_cont(uuid, uuid) to service_role;

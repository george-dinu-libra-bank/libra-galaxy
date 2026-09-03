-- =============================================================================
-- 0054 — tema grupului: culoarea de accent, emblema si fundalul
--
-- Pana acum toate grupurile aratau la fel: acelasi cerc albastru cu iconita
-- `Users` in lista, acelasi hero albastru pe pagina grupului. Intr-o lista de
-- zece grupuri („Colegi", „Familie", „Vacanta", „Chirie") numele era singurul
-- semn dupa care le deosebeai.
--
-- Aici se adauga trei coloane, toate pe `groups` — sunt ale grupului, nu ale
-- omului care se uita la el: doi membri deschid acelasi grup si vad aceeasi
-- tema.
--
--   1. `groups.tema` — culoarea de accent. Numele unei presetari, nu un hex:
--      rampa 50→900 traieste in frontend/src/app/globals.css (`.tema-grup-*`),
--      iar frontend/src/lib/tema-grup.ts leaga numele de clasa. Acelasi tipar
--      ca `carduri.card_style` din 0003_card_style.sql — text + check, nu jsonb
--      si nu hex in baza. Motivul e contrastul: fiecare presetare a fost
--      verificata pe perechile pe care le deseneaza efectiv aplicatia (alb pe
--      600, 700 pe 50, 600 pe alb), iar o culoare libera aleasa de utilizator
--      n-ar avea cine sa o verifice. Un galben deschis pus ca `primary-600` ar
--      face textul alb ilizibil — exact problema pe care a avut-o cardul
--      `gold`, vezi comentariul din lib/stil-card.ts.
--
--   2. `groups.emblema` — iconita lucide a grupului. Se pastreaza tot cheia
--      („plane"), nu componenta: baza nu stie nimic despre lucide-react.
--
--   3. `groups.fundal` — tapetul din spatele paginii grupului, peste cerul
--      instelat al aplicatiei (.fundal-spatial). Tot presetari, si tot fara
--      hex: fiecare model e desenat in CSS din rampa de accent a grupului
--      (`color-mix` peste `--color-primary-*`), deci cele 8 modele × 8 culori
--      dau 64 de fundaluri din 8 clase, si niciunul nu poate iesi din paleta.
--      De aceea nu sunt imagini: un JPEG n-ar urma culoarea aleasa, ar trebui
--      livrat in doua variante pentru tema deschisa si cea intunecata, si n-ar
--      avea cine sa-i garanteze contrastul cu textul de deasupra.
--      `implicit` inseamna „lasa cerul aplicatiei", deci nu se deseneaza nimic.
--
-- Cine poate schimba
--
-- Spre deosebire de drepturile din 0053, tema NU e rezervata creatorului: o
-- schimba orice membru, pentru tot grupul. Nu e o parghie asupra banilor sau
-- asupra a ce vede cine — e felul in care arata locul comun, si e corect sa fie
-- comun si el. Garda din seteaza_tema_grup e deci apartenenta la grup, nu
-- `id_creator`.
--
-- Pe `public.groups` nu exista politica de UPDATE (vezi 0000, „grupuri proprii:
-- select" e singura), deci scrierea trece obligatoriu printr-o functie
-- SECURITY DEFINER, la fel ca seteaza_vizibilitate_tranzactii_grup din 0053.
--
-- Grupurile existente
--
-- Defaultul ('implicit' + 'users' + 'implicit') e exact ce se desena si inainte, deci
-- migratia nu schimba aspectul niciunui grup deja creat. Din acelasi motiv
-- `creeaza_grup` (0000_instantaneu_inainte_de_credite.sql) nu se atinge:
-- randul nou primeste defaultul de coloana.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Coloanele
-- -----------------------------------------------------------------------------

alter table public.groups
  add column if not exists tema text not null default 'implicit',
  add column if not exists emblema text not null default 'users',
  add column if not exists fundal text not null default 'implicit';

alter table public.groups
  drop constraint if exists groups_tema_check;

alter table public.groups
  add constraint groups_tema_check
  check (tema in (
    'implicit', 'smarald', 'turcoaz', 'ametist',
    'zmeura', 'chihlimbar', 'scortisoara', 'grafit'
  ));

alter table public.groups
  drop constraint if exists groups_emblema_check;

alter table public.groups
  add constraint groups_emblema_check
  check (emblema in (
    'users', 'home', 'plane', 'party',
    'briefcase', 'heart', 'graduation', 'basket'
  ));

alter table public.groups
  drop constraint if exists groups_fundal_check;

alter table public.groups
  add constraint groups_fundal_check
  check (fundal in (
    'implicit', 'simplu', 'buline', 'grila',
    'romburi', 'diagonale', 'valuri', 'stropi'
  ));

comment on column public.groups.tema is
  'Culoarea de accent a grupului. Numele presetarii; rampa e in globals.css (.tema-grup-*), maparea in lib/tema-grup.ts.';
comment on column public.groups.emblema is
  'Iconita lucide a grupului. Cheia, nu componenta — vezi EMBLEME_GRUP din lib/tema-grup.ts.';
comment on column public.groups.fundal is
  'Modelul de fundal al paginii grupului, desenat in CSS din rampa de accent (.fundal-grup-* din globals.css). "implicit" = cerul aplicatiei.';


-- -----------------------------------------------------------------------------
-- 2. Setarea temei
-- -----------------------------------------------------------------------------

/**
 * Schimba tema grupului. Orice membru poate, si o vad toti.
 *
 * Cele trei valori se scriu impreuna: drawerul le trimite oricum pe toate, iar
 * un `update` unic tine si `modificat_la` (pus de trigger-ul
 * groups_before_update) sincron cu ce s-a schimbat de fapt.
 *
 * Listele de valori sunt duplicate fata de constraint-urile de mai sus, si asta
 * e intentionat: constraint-ul apara datele, dar arunca o eroare Postgres
 * generica pe care interfata n-o poate traduce. Codurile de aici (TEMA_INVALIDA
 * / EMBLEMA_INVALIDA / FUNDAL_INVALID) ajung in `error.message` si au traducere
 * in lib/actions/grupuri.ts::MESAJE_GRUPURI. Cand se adauga o presetare noua, se
 * schimba in amandoua locurile — plus globals.css si lib/tema-grup.ts.
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
    'romburi', 'diagonale', 'valuri', 'stropi'
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

-- Chemata doar din server actions Next.js, cu sesiunea utilizatorului. Backendul
-- Python nu stie nimic despre grupuri (zero referinte la „groups" in backend/app),
-- deci nu are nevoie de service_role.
--
-- Functiile din 0053 se bazeaza pe grantul implicit catre PUBLIC si se apara
-- doar prin `auth.uid()`. Aici stram putin mai tare, fiindca `get_advisors`
-- semnaleaza exact tiparul „SECURITY DEFINER expus ca RPC pentru anon"
-- (REGULI.md §3). Bariera reala ramane tot verificarea de apartenenta de mai sus.
revoke all on function public.seteaza_tema_grup(bigint, text, text, text) from public;
grant execute on function public.seteaza_tema_grup(bigint, text, text, text) to authenticated;

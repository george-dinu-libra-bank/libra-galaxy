-- =============================================================================
-- 0028 — Pasul B: completarea contului pentru cardurile existente
--
-- Se ruleaza DUPA 0027 si SE CITESTE INAINTE DE A FI RULAT.
--
-- Regula de completare e aceeasi pe care o aplica azi `creeaza_plata` cand alege
-- contul: cel mai vechi cont al aceluiasi utilizator, preferand RON. Alegerea
-- nu e arbitrara — e chiar comportamentul curent, inghetat. Astfel, dupa
-- migrare, fiecare card plateste din exact contul din care platea si pana acum,
-- si nimeni nu observa vreo schimbare.
--
-- Cardurile unui utilizator fara niciun cont raman cu `id_cont` null. Nu e o
-- scapare: 0029 (`not null`) va esua zgomotos in cazul asta, ceea ce e corect —
-- inseamna ca exista un card orfan care trebuie rezolvat manual, nu ascuns.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. INSPECTIE — ruleaza intai ASTA, singura, si citeste rezultatul.
--
-- Fiecare rand arata ce cont urmeaza sa primeasca fiecare card. Daca ceva pare
-- gresit, opreste-te aici: nimic nu s-a schimbat inca.
-- -----------------------------------------------------------------------------

select
  c.id                                   as id_card,
  right(c.numar_card, 4)                 as card,
  p.nume                                 as titular,
  cont_ales.nume                         as cont_propus,
  cont_ales.valuta,
  cont_ales.sold,
  case when cont_ales.id is null then 'FARA CONT — necesita atentie' else 'ok' end as stare
from public.carduri c
join public.profiles p on p.id = c.id_user
left join lateral (
  select b.*
    from public.conturi_bancare b
   where b.id_user = c.id_user
   order by (b.valuta = 'RON') desc, b.creat_la asc
   limit 1
) as cont_ales on true
order by p.nume, c.creat_la;


-- -----------------------------------------------------------------------------
-- 2. APLICAREA — ruleaza abia dupa ce tabelul de mai sus arata bine.
--
-- `where c.id_cont is null` face interogarea repetabila: rulata de doua ori, a
-- doua oara nu mai atinge nimic si nu suprascrie o legatura pusa manual intre
-- timp.
-- -----------------------------------------------------------------------------

update public.carduri c
   set id_cont = cont_ales.id
  from (
    select
      k.id as id_card,
      (select b.id
         from public.conturi_bancare b
        where b.id_user = k.id_user
        order by (b.valuta = 'RON') desc, b.creat_la asc
        limit 1) as id
    from public.carduri k
   ) as cont_ales
 where cont_ales.id_card = c.id
   and cont_ales.id is not null
   and c.id_cont is null;


-- -----------------------------------------------------------------------------
-- 3. VERIFICARE — cate carduri au ramas fara cont.
-- Daca intoarce 0, poti rula 0029.
-- -----------------------------------------------------------------------------

select count(*) as carduri_fara_cont
  from public.carduri
 where id_cont is null;

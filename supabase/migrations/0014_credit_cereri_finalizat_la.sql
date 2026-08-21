-- =============================================================================
-- Libra — `finalizat_la` se completeaza singur
--
-- 0013 a adaugat coloana, dar cine o scrie? Statusul unei cereri se schimba din
-- trei locuri diferite: `_finalizeaza` si `decide_manual` din Python, si RPC-ul
-- `credit_acorda` din 0010, care trece cererea in 'acceptata' direct din SQL.
--
-- Trei locuri inseamna trei sanse ca unul sa fie uitat la urmatoarea modificare,
-- iar consecinta ar fi tacuta: un dosar fara `finalizat_la` nu intra niciodata
-- in curatare, deci adeverinta lui ramane in storage pentru totdeauna. Nimeni
-- n-ar observa, fiindca nimic nu se strica vizibil.
--
-- Un trigger muta raspunderea intr-un singur loc, prin care trec toate trei.
-- =============================================================================

create or replace function public.credit_cereri_marcheaza_finalul()
returns trigger
language plpgsql
set search_path = ''
as $functie$
begin
  if new.status in ('respinsa', 'acceptata', 'anulata', 'expirata') then
    -- `is null` si nu suprascriere: daca dosarul e rescris din alt motiv,
    -- momentul inchiderii ramane cel dintai, nu cel al ultimei atingeri.
    if new.finalizat_la is null then
      new.finalizat_la := now();
    end if;
  else
    -- O cerere intoarsa in analiza (se intampla la confirmarea unei adeverinte)
    -- nu mai e inchisa, deci nici retentia nu mai curge. Fara ramura asta,
    -- documentul unui dosar redeschis s-ar sterge cat timp e inca in lucru.
    new.finalizat_la := null;
  end if;

  return new;
end;
$functie$;

drop trigger if exists credit_cereri_before_write on public.credit_cereri;
create trigger credit_cereri_before_write
  before insert or update on public.credit_cereri
  for each row
  execute function public.credit_cereri_marcheaza_finalul();

-- Cererile inchise inainte de migrare n-au momentul inchiderii. `creat_la` e o
-- aproximare buna in defavoarea noastra: retentia lor incepe mai devreme decat
-- in realitate, deci documentele lor se sterg mai repede, nu mai tarziu.
update public.credit_cereri
   set finalizat_la = creat_la
 where finalizat_la is null
   and status in ('respinsa', 'acceptata', 'anulata', 'expirata');

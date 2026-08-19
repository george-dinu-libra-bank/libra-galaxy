-- =============================================================================
-- Libra — tematica cardului (card_style)
--
-- Adauga coloana card_style pe public.carduri (peste schema din
-- 0002_carduri_tranzactii.sql). Utilizatorul alege tematica la creare —
-- standard, silver sau gold; restul campurilor (numar, CCV, expirare) tot in
-- trigger se genereaza, neschimbat fata de 0002.
--
-- Idempotent: functioneaza si daca tabela a fost creata deja manual cu o
-- coloana card_style simpla (text, fara default/constrangere).
-- =============================================================================

alter table public.carduri
  add column if not exists card_style text;

alter table public.carduri alter column card_style set default 'standard';
update public.carduri set card_style = 'standard' where card_style is null;
alter table public.carduri alter column card_style set not null;

alter table public.carduri drop constraint if exists carduri_stil_check;
alter table public.carduri
  add constraint carduri_stil_check check (card_style in ('standard', 'silver', 'gold'));

comment on column public.carduri.card_style is 'Tematica aleasa la creare: standard, silver sau gold.';

-- Card_style este imutabil din client dupa creare, la fel ca numar_card/ccv/
-- data_expirare — extindem functia din 0002_carduri_tranzactii.sql ca sa-l
-- protejeze si pe el la UPDATE.
create or replace function public.carduri_protejeaza_campuri()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.id            := old.id;
  new.id_user       := old.id_user;
  new.numar_card    := old.numar_card;
  new.data_expirare := old.data_expirare;
  new.ccv           := old.ccv;
  new.card_style    := old.card_style;
  new.creat_la      := old.creat_la;
  new.modificat_la  := now();

  -- Din aplicatie se poate schimba doar is_blocked; soldul vine din backend.
  if auth.role() <> 'service_role' then
    new.sold_curent := old.sold_curent;
  end if;

  return new;
end;
$$;

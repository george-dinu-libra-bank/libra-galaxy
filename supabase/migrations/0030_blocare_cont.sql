-- =============================================================================
-- 0030 — Blocarea administrativa, la nivel de cont si etansa in baza
--
-- Doua probleme se rezolva aici.
--
-- 1. `carduri.is_blocked` amesteca doua lucruri diferite: butonul prin care
--    CLIENTUL isi blocheaza un card pierdut, si masura pe care o ia un
--    ADMINISTRATOR. Cum `lib/cont-blocat.ts` numara orice card blocat al omului
--    ca sa refuze transferurile, un client care isi bloca propriul card ramanea
--    fara transferuri, cu mesajul "Contul tau este blocat temporar". Defect
--    real, nu ipotetic.
--
-- 2. Blocarea administrativa traia doar in aplicatie. `core_banking` si
--    `core_banking_groups` nu ating deloc cardurile, deci cine chema RPC-ul
--    direct cu tokenul lui trecea pe langa. Recunoscut deschis in 0020.
--
-- Solutia: un steag pe CONT, si o garda in baza care refuza orice iesire de bani
-- din contul blocat.
--
-- Garda e un trigger pe `conturi_bancare`, nu o rescriere a celor trei functii
-- de bani. Motivul e ca prinde ORICE drum prin care scade soldul — cele trei
-- functii de azi, operatiunile de credit, si orice s-ar adauga maine — fara sa
-- reproduc corpul unor functii mari si delicate, cu riscul de a schimba tacut
-- altceva pe drum.
-- =============================================================================

alter table public.conturi_bancare
  add column if not exists blocat_administrativ boolean not null default false;

comment on column public.conturi_bancare.blocat_administrativ is
  'Oprit de un administrator. Banii nu mai pot iesi din cont, dar pot intra.';

create index if not exists conturi_blocat_idx
  on public.conturi_bancare (id_user)
  where blocat_administrativ;


-- -----------------------------------------------------------------------------
-- Garda
--
-- Banii pot INTRA intr-un cont blocat (o rambursare, un salariu, o corectie),
-- dar nu pot iesi. Un cont in care nu mai poate intra nimic ar transforma
-- blocarea intr-o pedeapsa asupra celor care ii trimit bani, nu asupra lui.
-- -----------------------------------------------------------------------------

create or replace function public.conturi_opreste_iesirile_daca_blocat()
returns trigger
language plpgsql
security definer
set search_path to ''
as $$
begin
  if old.blocat_administrativ and new.sold < old.sold then
    raise exception 'CONT_BLOCAT'
      using detail = 'Contul este blocat de banca; banii nu pot iesi din el.';
  end if;
  return new;
end;
$$;

drop trigger if exists conturi_before_update_blocare on public.conturi_bancare;

create trigger conturi_before_update_blocare
  before update on public.conturi_bancare
  for each row execute function public.conturi_opreste_iesirile_daca_blocat();


-- -----------------------------------------------------------------------------
-- `analize_cont.carduri_blocate` numara acum conturi, nu carduri
--
-- Coloana a fost adaugata in 0020, cand masura administratorului se aplica pe
-- carduri. Acum se aplica pe conturi, deci numele minte. E tabela introdusa tot
-- de noi si nu are inca decizii scrise in ea, asa ca redenumirea nu strica
-- istoric.
-- -----------------------------------------------------------------------------

alter table public.analize_cont
  rename column carduri_blocate to conturi_blocate;

comment on column public.analize_cont.conturi_blocate is
  'Cate conturi a atins decizia (blocate sau deblocate).';

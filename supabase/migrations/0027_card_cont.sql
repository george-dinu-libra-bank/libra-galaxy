-- =============================================================================
-- 0027 — Pasul A: cardul primeste un cont
--
-- Pana acum un card apartinea direct unui utilizator, iar contul din care se
-- luau banii se alegea la FIECARE plata, printr-o euristica din `creeaza_plata`:
-- primul cont al omului care acopera suma, preferand valuta comerciantului.
-- Cardul nu juca niciun rol.
--
-- Consecinta, masurata pe baza reala: trei utilizatori au simultan mai multe
-- carduri si mai multe conturi (unul dintre ei RON + EUR), deci din ce cont
-- plateste un anume card era nedecidabil. Un card "de vacanta" putea goli tacut
-- contul curent.
--
-- Migrarea asta face DOAR primul pas: adauga coloana, nullable. Nimic nu se
-- strica, fiindca tot codul de azi o ignora. Completarea valorilor e in 0028,
-- iar `not null` in 0029 — separate deliberat, ca fiecare pas sa poata fi citit
-- si verificat inainte de urmatorul.
-- =============================================================================

alter table public.carduri
  add column if not exists id_cont uuid references public.conturi_bancare (id) on delete restrict;

comment on column public.carduri.id_cont is
  'Contul din care plateste acest card. Banii stau pe cont, nu pe card.';

-- `on delete restrict`, nu `cascade`: un cont cu carduri active nu trebuie sa
-- dispara tacut, luand cardurile cu el. Cine vrea sa inchida contul muta sau
-- blocheaza intai cardurile, deliberat.

create index if not exists carduri_id_cont_idx on public.carduri (id_cont);

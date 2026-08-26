-- =============================================================================
-- 0034 — stergerea unui cont nu mai pica, iar istoricul arata "Cont sters"
--
-- CAUZA REALA, obtinuta abia dupa ce am ocolit GoTrue si am sters randul din
-- profiles direct prin PostgREST (auth raspunde doar cu genericul
-- "Database error deleting user", care nu spune nimic):
--
--   insert or update on table "tranzactii" violates foreign key constraint
--   "tranzactii_id_cont_send_fkey"
--   Key (id_cont_send)=(...) is not present in table "conturi_bancare".
--
-- La stergerea unui profil, `conturi_bancare` si `carduri` dispar prin cascada,
-- dar randurile din `tranzactii` raman (asa e gandit: istoricul supravietuieste
-- stergerii unui cont — vezi comentariul tabelei din 0002). Ca sa ramana valide,
-- referintele lor catre cont si card trebuie golite automat, adica ON DELETE SET
-- NULL. In baza reala nu erau asa, desi instantaneul 0000 (liniile 1900-1912)
-- sustine ca sunt: fisierele de migratie au divergat de proiectul din cloud
-- (REGULI.md #2). De aceea migratia asta REPARA cheile, nu doar le documenteaza.
--
-- Se repara toate patru, nu doar cea care a aparut in eroare: prima violare
-- opreste instructiunea, deci celelalte trei n-ar fi iesit la iveala decat pe
-- rand, la fiecare incercare urmatoare.
--
-- Aditiva si idempotenta: se poate rula de doua ori fara alt efect.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Referintele din istoric se golesc cand contul sau cardul dispare
--
-- ON DELETE SET NULL nu e suficient singur, si merita explicat de ce, pentru ca
-- e contraintuitiv. Stergerea unui profil declanseaza mai multe actiuni pe
-- ACELASI rand din tranzactii:
--
--   * id_user_send    -> null  (profilul dispare)
--   * id_user_recieve -> null  (la un transfer intre conturile proprii, acelasi
--                               om e pe ambele capete)
--   * id_cont_send    -> null  (contul bancar dispare in cascada)
--   * id_cont_recieve -> null
--
-- Postgres le executa una cate una, ca UPDATE-uri succesive pe acelasi rand.
-- Fiecare UPDATE reverifica cheile straine ale randului, iar verificarea pentru
-- id_cont_send ruleaza inainte ca actiunea ei proprie sa fi apucat sa goleasca
-- valoarea — cand contul a fost deja sters. Rezultat:
--
--   insert or update on table "tranzactii" violates foreign key constraint
--   "tranzactii_id_cont_send_fkey"
--
-- DEFERRABLE INITIALLY DEFERRED muta verificarile la COMMIT, cand toate
-- actiunile s-au terminat si randul si-a atins forma finala (toate null).
-- Atunci trec toate.
--
-- Pretul, ca sa fie scris: o violare reala de cheie straina nu mai apare la
-- instructiunea vinovata, ci la commit, deci mesajul de eroare indica mai vag
-- unde s-a gresit. Pe o tabela de istoric care nu se editeaza din aplicatie,
-- schimbul e in regula.
-- -----------------------------------------------------------------------------
alter table public.tranzactii
  drop constraint if exists tranzactii_id_cont_send_fkey;
alter table public.tranzactii
  add constraint tranzactii_id_cont_send_fkey
  foreign key (id_cont_send) references public.conturi_bancare (id) on delete set null
  deferrable initially deferred;

alter table public.tranzactii
  drop constraint if exists tranzactii_id_cont_recieve_fkey;
alter table public.tranzactii
  add constraint tranzactii_id_cont_recieve_fkey
  foreign key (id_cont_recieve) references public.conturi_bancare (id) on delete set null
  deferrable initially deferred;

alter table public.tranzactii
  drop constraint if exists tranzactii_id_card_send_fkey;
alter table public.tranzactii
  add constraint tranzactii_id_card_send_fkey
  foreign key (id_card_send) references public.carduri (id) on delete set null
  deferrable initially deferred;

alter table public.tranzactii
  drop constraint if exists tranzactii_id_card_recieve_fkey;
alter table public.tranzactii
  add constraint tranzactii_id_card_recieve_fkey
  foreign key (id_card_recieve) references public.carduri (id) on delete set null
  deferrable initially deferred;


-- -----------------------------------------------------------------------------
-- 2. Regula "macar o parte" se muta de pe CHECK pe un trigger de INSERT
--
-- `tranzactii_parti_check` cere ca macar una dintre parti sa fie non-null. Un
-- transfer intre conturile aceleiasi persoane are acelasi om la ambele capete,
-- deci la stergerea lui ambele coloane devin null si check-ul pica.
--
-- Constrangerea e corecta ca intentie, dar e o regula despre CE SE INSEREAZA,
-- nu despre ce ramane dupa ce un cont dispare: un rand de istoric fara niciun
-- participant e in continuare inregistrarea valida a unei sume si a unei date.
-- Pe trigger de INSERT, intentia se pastreaza fara sa mai blocheze stergerea.
--
-- (In baza actuala constrangerea pare sa nu existe — stergerea unui cont de
-- test cu transfer catre sine a mers si fara migratia asta. `drop ... if
-- exists` o trateaza ca pe un no-op, iar trigger-ul acopera cazul oricum.)
-- -----------------------------------------------------------------------------
alter table public.tranzactii
  drop constraint if exists tranzactii_parti_check;

create or replace function public.tranzactii_cere_o_parte()
returns trigger
language plpgsql
set search_path = ''
as $functie$
begin
  if new.id_user_send is null
     and new.id_user_recieve is null
     and new.id_group_send is null
     and new.id_group_recieve is null then
    raise exception 'O tranzactie trebuie sa aiba macar o parte (utilizator sau grup).'
      using errcode = '23514';
  end if;

  return new;
end;
$functie$;

comment on function public.tranzactii_cere_o_parte() is
  'Inlocuieste vechiul tranzactii_parti_check. Ruleaza doar la INSERT, ca golirea referintelor la stergerea unui cont sa nu fie tratata ca date invalide.';

drop trigger if exists tranzactii_cere_o_parte on public.tranzactii;

create trigger tranzactii_cere_o_parte
  before insert on public.tranzactii
  for each row
  execute function public.tranzactii_cere_o_parte();


-- -----------------------------------------------------------------------------
-- 3. Marcajul "Cont sters" din istoric
--
-- Pana acum interfata afisa "Cont Galaxy Bank" pentru orice contraparte lipsa,
-- deci nu se putea face diferenta intre un cont sters si celelalte ~500 de
-- randuri care au o parte null din alte motive (miscari de sistem, depuneri in
-- grup). De aceea marcam explicit, la stergere, care parte a disparut.
--
-- Se marcheaza CU UN BOOLEAN, nu cu numele salvat: un cont sters trebuie sa
-- dispara, iar pastrarea numelui in istoric ar contrazice chiar stergerea.
-- -----------------------------------------------------------------------------
alter table public.tranzactii
  add column if not exists send_sters    boolean not null default false,
  add column if not exists recieve_sters boolean not null default false;

comment on column public.tranzactii.send_sters is
  'True daca expeditorul era un cont care intre timp a fost sters. Se pune automat la stergerea profilului; interfata afiseaza "Cont sters" in loc de nume.';

comment on column public.tranzactii.recieve_sters is
  'Ca send_sters, pentru destinatar.';

-- Marcajul se pune AGATANDU-SE de update-ul pe care ON DELETE SET NULL il face
-- oricum pe rand, nu printr-un UPDATE separat.
--
-- Prima varianta a fost un trigger BEFORE DELETE pe profiles, care rula
-- `update tranzactii set send_sters = true where id_user_send = old.id`. Nu
-- merge, si esecul e instructiv: acel UPDATE atinge randuri care, in aceeasi
-- comanda, sunt si tinta actiunii SET NULL pornite de stergerea conturilor
-- bancare. Verificarea de cheie straina pentru id_cont_send ajunge sa ruleze
-- dupa ce contul a disparut, si stergerea pica cu
-- "violates foreign key constraint tranzactii_id_cont_send_fkey" — exact
-- eroarea pe care migratia asta o repara mai sus, doar ca provocata de leac,
-- nu de boala.
--
-- Varianta de aici n-are cum sa intre in conflict: nu executa niciun UPDATE
-- propriu, ci doar completeaza randul care oricum se rescrie. Fara
-- SECURITY DEFINER, fiindca modifica doar NEW, nu scrie in alta tabela.
create or replace function public.tranzactii_marcheaza_cont_sters()
returns trigger
language plpgsql
set search_path = ''
as $functie$
begin
  -- Trecerea din "avea utilizator" in "nu mai are" se intampla intr-un singur
  -- caz: contul a fost sters, iar cheia straina i-a golit referinta.
  if old.id_user_send is not null and new.id_user_send is null then
    new.send_sters := true;
  end if;

  if old.id_user_recieve is not null and new.id_user_recieve is null then
    new.recieve_sters := true;
  end if;

  return new;
end;
$functie$;

comment on function public.tranzactii_marcheaza_cont_sters() is
  'Marcheaza in istoric partile care apartineau contului sters, ca interfata sa poata scrie "Cont sters" in loc sa confunde cazul cu o tranzactie de sistem.';

-- Varianta veche, gresita, daca a apucat sa fie aplicata.
drop trigger if exists profiles_marcheaza_tranzactii on public.profiles;

drop trigger if exists tranzactii_marcheaza_cont_sters on public.tranzactii;

create trigger tranzactii_marcheaza_cont_sters
  before update on public.tranzactii
  for each row
  execute function public.tranzactii_marcheaza_cont_sters();


-- -----------------------------------------------------------------------------
-- Ce NU face migratia, deliberat:
--
--   * nu completeaza retroactiv send_sters/recieve_sters. Pentru randurile
--     existente cu o parte null nu se mai poate sti daca acolo a fost vreodata
--     un cont sters sau daca partea a lipsit dintotdeauna, iar a ghici ar
--     insemna sa scrie "Cont sters" peste ~500 de miscari de sistem.
--   * nu sterge randurile ramase fara nicio parte. Sunt invizibile pentru
--     toata lumea, dar tabela e explicit un istoric care supravietuieste
--     stergerii unui cont (vezi comentariul tabelei din 0002).
-- -----------------------------------------------------------------------------

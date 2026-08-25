-- =============================================================================
-- Libra — canalul dintre analist si client, plus starea "asteapta documente"
--
-- Pana acum analistul avea doua iesiri dintr-un dosar din zona gri: aproba sau
-- respinge. Nu putea cere un act si nu putea spune clientului ca ceva nu se
-- leaga, fara sa inchida dosarul. Migrarea adauga starea intermediara si locul
-- in care sta mesajul.
--
-- Strict aditiva: largeste o constrangere de check si adauga doua coloane care
-- accepta null. Nu sterge randuri, nu schimba date existente, si se poate rula
-- de doua ori fara alt efect.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Starea in care mingea e la client
--
-- Distincta de 'analiza_manuala' dinadins: acolo asteapta banca, aici asteapta
-- clientul. Daca ar fi aceeasi stare, dosarul ar ramane in coada analistului
-- desi el n-are ce face, iar clientului i s-ar spune "un coleg se uita peste
-- dosar" cand de fapt el trebuie sa actioneze.
--
-- NU intra in STATUSURI_FINALE din credit_service.py: dosarul e deschis, deci
-- primeste in continuare documente, iar retentia nu incepe sa curga.
-- -----------------------------------------------------------------------------
alter table public.credit_cereri drop constraint if exists credit_cereri_status_check;
alter table public.credit_cereri
  add constraint credit_cereri_status_check check (status in (
    'ciorna', 'in_analiza', 'oferta', 'analiza_manuala', 'asteapta_documente',
    'respinsa', 'acceptata', 'anulata', 'expirata'
  ));


-- -----------------------------------------------------------------------------
-- 2. Mesajul analistului catre client
--
-- Coloana proprie, nu `explicatie`, desi amandoua ajung sub ochii clientului.
-- `explicatie` e rescrisa de motor la fiecare reevaluare (vezi `_finalizeaza`),
-- iar fluxul pentru care exista mesajul — "cer acte, clientul incarca, se
-- reevalueaza" — l-ar sterge exact atunci cand conteaza.
--
-- Cele doua se citesc impreuna in interfata: motivarea deciziei vine de la
-- masina, mesajul vine de la un om, si e util sa se vada care e care.
-- -----------------------------------------------------------------------------
alter table public.credit_cereri
  add column if not exists mesaj_analist    text,
  add column if not exists mesaj_analist_la timestamptz;

comment on column public.credit_cereri.mesaj_analist is
  'Text scris de un analist pentru client (cerere de acte sau semnalarea unei probleme). Separat de `explicatie`, care e generata de motor si se rescrie la fiecare reevaluare.';
comment on column public.credit_cereri.mesaj_analist_la is
  'Cand a fost scris mesajul. Fara el nu se poate spune daca mesajul e de dinainte sau de dupa ultima incarcare de document.';


-- -----------------------------------------------------------------------------
-- 3. Coada analistului
--
-- Indexul partial din 0009 acopera doar 'analiza_manuala'. Dosarele care asteapta
-- documente se citesc la fel de des (interfata are filtru propriu pentru ele),
-- deci merita acelasi tratament.
-- -----------------------------------------------------------------------------
create index if not exists credit_cereri_asteapta_documente_idx
  on public.credit_cereri (creat_la)
  where status = 'asteapta_documente';

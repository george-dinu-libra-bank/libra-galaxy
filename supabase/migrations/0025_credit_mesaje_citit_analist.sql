-- Simetricul lui `citit_de_client_la` din 0024, pentru cealalta parte a firului.
--
-- Pana acum necititul era unidirectional prin proiectare: clientul vedea o
-- bulina cand ii scria banca, dar banca nu afla ca a primit un mesaj.
-- `scrie_mesaj_client` nu scria eveniment, nu notifica si nu schimba starea, iar
-- `CerereAdminResponse` nu expunea niciun contor. Un dosar in 'asteapta_documente'
-- in care clientul a scris „nu inteleg ce vreti" statea acolo pana se uita
-- cineva din intamplare.
--
-- Doua coloane, nu una cu rol dublu: fiecare parte citeste in ritmul ei, iar o
-- singura coloana ar face ca deschiderea firului de catre analist sa stinga si
-- bulina clientului.

alter table public.credit_mesaje
  add column if not exists citit_de_analist_la timestamptz;

comment on column public.credit_mesaje.citit_de_analist_la is
  'Cand a deschis analistul firul dupa acest mesaj. Null = necitit de banca. '
  'Se completeaza doar pentru autor = ''client'' — mesajele proprii si cele '
  'de sistem n-au ce sa-i semnaleze.';

-- Index partial, ca la 0024: interogarea de numarare cauta exact randurile
-- ramase necitite, care sunt putine. Un index pe toata coloana ar creste cu
-- fiecare mesaj citit, fara sa fie folosit vreodata pentru ele.
create index if not exists credit_mesaje_necitite_analist_idx
  on public.credit_mesaje (id_cerere)
  where citit_de_analist_la is null and autor = 'client';

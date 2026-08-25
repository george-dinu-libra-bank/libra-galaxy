-- =============================================================================
-- Libra — marcaj de citit pe firul dosarului de credit
--
-- Bulina "ai mesaje noi" are nevoie de o sursa proprie. Ar fi putut fi numarul
-- de notificari necitite, dar atunci "marcheaza tot ca citit" din clopotel ar
-- fi stins si bulina din credite, desi omul n-a deschis firul. Marcajul sta pe
-- mesaj, deci raspunde exact la intrebarea pusa: "ce n-am citit din discutie?".
--
-- Doar clientul are marcaj: analistul isi vede firul in dosar, unde ajunge
-- oricum ca sa decida, deci un contor pentru el n-ar fi folosit la nimic.
-- =============================================================================
alter table public.credit_mesaje
  add column if not exists citit_de_client_la timestamptz;

comment on column public.credit_mesaje.citit_de_client_la is
  'Cand a deschis clientul firul dupa acest mesaj. Null = necitit. Se completeaza doar pentru mesajele care nu sunt ale lui.';

-- Numararea necititelor se face la fiecare afisare a listei de cereri, deci
-- merita index. Partial: randurile deja citite nu se mai numara niciodata.
create index if not exists credit_mesaje_necitite_idx
  on public.credit_mesaje (id_cerere)
  where citit_de_client_la is null;

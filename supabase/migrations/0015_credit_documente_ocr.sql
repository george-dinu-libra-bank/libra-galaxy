-- =============================================================================
-- Libra — adeverinta de venit: ce s-a citit din ea, cine a confirmat, cat sta
--
-- 0009 a pregatit terenul (tabela credit_documente, bucket-ul credit-documente,
-- sursa 'adeverinta' in credit_verificari_venit) dar nimic nu il folosea. Aici se
-- adauga ce lipsea ca documentul sa treaca prin mana unui om si sa dispara dupa.
--
-- Migrarea e ADITIVA: adauga coloane care accepta null, largeste o constrangere
-- de check si pune limite pe un bucket care nu avea niciuna. Nu sterge randuri,
-- nu schimba date existente, si se poate rula de doua ori fara alt efect.
-- =============================================================================

-- Numerotare: aplicata initial ca 0013, renumerotata la 0015 dupa ce s-a
-- descoperit ca un coleg are deja un 0013_schimb_valutar.sql aplicat in baza
-- reala (public.schimba_valuta_cont exista, conturi_bancare.valuta exista), doar
-- ca fisierul lui nu e inca pe git. 0013 si 0014 raman libere pentru el.
--
-- Exact coliziunea despre care avertizeaza REGULI.md #3: doi oameni care pornesc
-- de la acelasi ultim numar cunoscut. Istoricul din supabase_migrations pastreaza
-- numele vechi — e o eticheta, nu o cheie, si nu se rescrie.

-- -----------------------------------------------------------------------------
-- 1. Ce stim despre document, dincolo de ce a citit masina
--
-- `venit_confirmat` si `confirmat_de` sunt separate de `extras`: acolo sta ce a
-- citit OCR-ul, aici ce a hotarat omul. Cand cele doua difera — si vor diferi —
-- se vede peste sase luni care a fost care. Daca am suprascrie `extras`, am
-- pierde exact dovada ca a fost nevoie de o corectie.
--
-- `hash_fisier` ramane dupa ce fisierul e sters. Fara el, un rand cu venitul
-- extras nu mai poate fi legat de nimic verificabil; cu el, daca cineva
-- pastreaza o copie a adeverintei, se poate dovedi ca e chiar aceea.
-- -----------------------------------------------------------------------------
alter table public.credit_documente
  add column if not exists hash_fisier     text,
  add column if not exists venit_confirmat numeric(14,2),
  add column if not exists confirmat_de    uuid references public.profiles (id) on delete set null,
  add column if not exists confirmat_la    timestamptz,
  add column if not exists sters_la        timestamptz;

comment on column public.credit_documente.hash_fisier is
  'SHA-256 al continutului. Supravietuieste stergerii fisierului: leaga randul de un document verificabil.';
comment on column public.credit_documente.venit_confirmat is
  'Cifra hotarata de analist. `extras` pastreaza separat ce citise OCR-ul.';
comment on column public.credit_documente.sters_la is
  'Cand a fost sters fisierul din storage. Randul ramane; fisierul, nu.';

-- Starea analizei, nu a fisierului: 'confirmat' inseamna ca un om a validat
-- cifra, indiferent daca fisierul mai exista (`sters_la` raspunde la aia).
alter table public.credit_documente drop constraint if exists credit_documente_status_check;
alter table public.credit_documente
  add constraint credit_documente_status_check
  check (status in ('incarcat', 'procesat', 'ilizibil', 'confirmat'));

-- Un document confirmat are si cine, si cat. Constrangerea prinde din start un
-- update partial, in loc sa lase un rand pe jumatate confirmat.
alter table public.credit_documente drop constraint if exists credit_documente_confirmare_check;
alter table public.credit_documente
  add constraint credit_documente_confirmare_check
  check (
    status <> 'confirmat'
    or (venit_confirmat is not null and confirmat_de is not null and confirmat_la is not null)
  );

-- Curatarea cauta documente cu fisier inca prezent. Indexul partial e mic:
-- contine doar randurile care mai au ceva de sters.
create index if not exists credit_documente_de_curatat_idx
  on public.credit_documente (id_cerere)
  where sters_la is null;


-- -----------------------------------------------------------------------------
-- 2. Cand s-a inchis dosarul
--
-- Retentia se masoara de la starea finala, nu de la incarcare: un dosar care sta
-- doua luni in analiza nu trebuie sa ramana fara dovezi tocmai cand se decide.
-- `credit_evenimente` ar fi putut da raspunsul, dar printr-o cautare la fiecare
-- trecere; o coloana e un singur camp citit.
-- -----------------------------------------------------------------------------
alter table public.credit_cereri
  add column if not exists finalizat_la timestamptz;

comment on column public.credit_cereri.finalizat_la is
  'Cand cererea a ajuns in respinsa/acceptata/anulata/expirata. Punctul de la care curge retentia documentelor.';


-- -----------------------------------------------------------------------------
-- 3. Limitele bucket-ului
--
-- `credit-documente` a fost creat in 0009 fara nicio limita, spre deosebire de
-- 'asistent-atasamente' (0005), care are si plafon de marime si allowlist de
-- tipuri. Aplicatia valideaza oricum inainte de upload, dar bucket-ul e ultima
-- bariera si trebuie sa fie la fel de stricta: cine ar ocoli aplicatia da tot
-- de ea.
-- -----------------------------------------------------------------------------
update storage.buckets
   set file_size_limit = 10485760,
       allowed_mime_types = array['application/pdf', 'image/png', 'image/jpeg', 'image/webp']
 where id = 'credit-documente';


-- -----------------------------------------------------------------------------
-- 4. Analistul vede documentul
--
-- 0012 a dat acces de administrator pe 'buletine' si 'selfie-uri', dar nu si
-- aici — creditarea nu exista inca atunci. Fara politica asta, analistul nu
-- poate genera un URL semnat catre adeverinta pe care trebuie sa o confirme.
--
-- Numai select: documentul se citeste, nu se rescrie. Bucket-ul ramane privat;
-- URL-ul semnat are durata scurta si se cere din backend.
-- -----------------------------------------------------------------------------
drop policy if exists "credit-documente: adminul vede documentele" on storage.objects;
create policy "credit-documente: adminul vede documentele"
  on storage.objects for select to authenticated
  using (bucket_id = 'credit-documente' and public.este_administrator());

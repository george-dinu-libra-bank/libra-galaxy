-- =============================================================================
-- 0050 — De unde a venit plata: adresa IP
--
-- RENUMEROTATA din 0047. Migrarea a fost scrisa cand 0047 era liber; intre timp
-- 0047-0049 au fost ocupate pe origin/main (poprirea si urmarile ei). Continutul
-- e neschimbat fata de varianta initiala, in afara de numar si de nota de la
-- `sterge_ip_vechi` de mai jos. Regula e in REGULI.md #3: la coliziune se
-- renumeroteaza una dintre migratii, nu se aleg conflict markers pe SQL.
--
-- Detectia de neregularitati se uita azi doar la suma, comerciant si ritm. Un
-- semnal care lipseste cu totul e locul: doua plati din tari diferite la cateva
-- minute distanta sunt imposibile fizic, indiferent cat de obisnuite ar fi
-- sumele.
--
-- Migrarea asta nu adauga niciun semnal. Adauga doar coloana in care el se
-- poate acumula — fara istoric, „deplasare imposibila" n-are cu ce compara, iar
-- o trasatura fara date strica modelul in loc sa-l ajute (masurat: 9/9 -> 7/9
-- cu o coloana constanta, vezi app/ml/antrenari.jsonl).
--
-- NU atinge `dispozitive_conectate`. Amprenta de dispozitiv apartine zonei de
-- securitate si se scrie la autentificare, nu la plata; aici e nevoie de locul
-- din momentul tranzactiei, care e altceva.
--
-- Date personale: o adresa IP identifica o persoana, deci intra sub GDPR.
-- Temeiul e prevenirea fraudei (interes legitim), iar retentia trebuie sa fie
-- limitata — vezi nota de la finalul fisierului.
-- =============================================================================

alter table public.payments
  add column if not exists ip inet;

comment on column public.payments.ip is
  'De unde a venit plata. Se completeaza la creare, din antetul cererii.';

alter table public.tranzactii
  add column if not exists ip inet;

comment on column public.tranzactii.ip is
  'De unde a venit transferul. Null pentru randurile de dinaintea 0050 si pentru miscarile generate de sistem (rate, dobanzi).';


-- Cautarea e mereu „ultimele plati ale acestui om", nu „cine a folosit IP-ul X":
-- indexul urmeaza intrebarea, nu coloana.
create index if not exists payments_user_ip_idx
  on public.payments (id_user, creat_la desc)
  where ip is not null;

create index if not exists tranzactii_send_ip_idx
  on public.tranzactii (id_user_send, creat_la desc)
  where ip is not null;


-- -----------------------------------------------------------------------------
-- Retentie
--
-- IP-ul e util pentru fereastra in care se compara doua tranzactii — ore, zile,
-- nu ani. Dupa 90 de zile nu mai spune nimic despre frauda, dar ramane un dat
-- personal pastrat degeaba.
--
-- Nu se ruleaza automat: proiectul n-are cron, iar o stergere programata pe care
-- nimeni n-o vede ruland e mai rea decat una manuala. Se cheama din curatenia
-- periodica, alaturi de celelalte.
--
-- SINGURA schimbare fata de varianta initiala: numaratoarea aduna ambele tabele.
-- Acolo `get diagnostics` era chemat doar dupa update-ul pe `payments`, iar
-- randurile din `tranzactii` se curatau dar nu se numarau — functia raporta mai
-- putin decat curatase. Intr-o rutina de retentie, cifra returnata e singura
-- dovada ca a facut ceva, deci merita sa fie cea adevarata.
-- -----------------------------------------------------------------------------

create or replace function public.sterge_ip_vechi(p_zile integer default 90)
returns integer
language plpgsql
security definer
set search_path to ''
as $$
declare
  v_sterse    integer := 0;
  v_partial   integer := 0;
  v_prag      timestamptz := now() - make_interval(days => greatest(p_zile, 1));
begin
  update public.payments set ip = null
   where ip is not null and creat_la < v_prag;
  get diagnostics v_sterse = row_count;

  update public.tranzactii set ip = null
   where ip is not null and creat_la < v_prag;
  get diagnostics v_partial = row_count;

  return v_sterse + v_partial;
end;
$$;

comment on function public.sterge_ip_vechi(integer) is
  'Sterge adresele IP mai vechi de p_zile din payments si tranzactii. '
  'Intoarce cate randuri au fost curatate, din ambele tabele.';

revoke all on function public.sterge_ip_vechi(integer) from public, anon, authenticated;
grant execute on function public.sterge_ip_vechi(integer) to service_role;

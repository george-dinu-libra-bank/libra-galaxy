-- -----------------------------------------------------------------------------
-- Libra — confirmarea documentelor: constrangerea priveste doar adeverintele
--
-- `credit_documente_confirmare_check` (0015) cerea ca orice rand cu
-- status='confirmat' sa aiba `venit_confirmat`, `confirmat_de` si
-- `confirmat_la`. Regula era scrisa cand singurul document real era adeverinta
-- de venit: acolo "confirmat" chiar inseamna ca un analist s-a uitat la hartie
-- si a hotarat o cifra.
--
-- De la 0037 in tabela intra si contractul semnat (tip='contract'), pus acolo
-- ca dosarul sa arate contractul in aceeasi lista cu adeverintele. Contractul
-- nu are venit de confirmat si nu il valideaza niciun analist — il semneaza
-- clientul, iar dovada semnaturii sta in `extras` (semnat_la, ip) si in
-- evenimentul `contract_semnat`. Cu vechea regula, insertul cadea cu 23514.
--
-- Deci constrangerea se restrange la tipul pentru care a fost scrisa:
-- adeverintele raman la fel de strict pazite, contractele intra confirmate din
-- start pentru ca nu mai au ce astepta.
-- -----------------------------------------------------------------------------

alter table public.credit_documente drop constraint if exists credit_documente_confirmare_check;
alter table public.credit_documente
  add constraint credit_documente_confirmare_check
  check (
    tip <> 'adeverinta_venit'
    or status <> 'confirmat'
    or (venit_confirmat is not null and confirmat_de is not null and confirmat_la is not null)
  );

comment on constraint credit_documente_confirmare_check on public.credit_documente is
  'O adeverinta confirmata are si cine, si cat. Contractul semnat e confirmat prin insasi semnatura clientului (vezi extras.semnat_la), fara venit si fara analist.';

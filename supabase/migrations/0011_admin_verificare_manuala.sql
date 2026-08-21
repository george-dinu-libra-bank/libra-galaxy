-- =============================================================================
-- Libra — verificarea manuala (fara dovezi) si urma completa de admin
--
-- Doua lucruri, aditive:
--   1. Constrangerea acces_actiune_check de la 0008 nu includea actiunile
--      folosite de panoul de verificari de identitate (lista_verificari,
--      vede_verificare, decide_verificare) — scrierea urmei esua tacut de
--      fiecare data (scrie_acces prinde orice exceptie si doar logheaza).
--   2. O actiune noua, forteaza_verificare: unele conturi raman in
--      verification_status = 'pending' (default la inregistrare) fara sa
--      treaca vreodata prin OCR+selfie — nu exista dovezi de revizuit, dar
--      administratorul poate alege sa le deblocheze manual.
-- =============================================================================

alter table public.acces_administrator drop constraint if exists acces_actiune_check;
alter table public.acces_administrator
  add constraint acces_actiune_check
  check (actiune in (
    'lista_alerte', 'raport_pdf', 'raport_csv',
    'lista_verificari', 'vede_verificare', 'decide_verificare',
    'lista_neincepute', 'forteaza_verificare'
  ));

-- =============================================================================
-- Libra — restabilirea manuala a referintei biometrice
--
-- Cand pozele din storage dispar (sterse manual, din greseala sau nu), userii
-- raman fara nimic de comparat la login biometric. Administratorul poate
-- restabili manual referinta: o poza noua, facuta de el impreuna cu userul
-- sau incarcata de acesta pe alta cale, devine noul reper.
--
-- Aditiva, ca 0011: doar extinde constrangerea acces_actiune_check cu cele
-- doua actiuni noi (lista tuturor conturilor, restabilirea in sine).
-- =============================================================================

alter table public.acces_administrator drop constraint if exists acces_actiune_check;
alter table public.acces_administrator
  add constraint acces_actiune_check
  check (actiune in (
    'lista_alerte', 'raport_pdf', 'raport_csv',
    'lista_verificari', 'vede_verificare', 'decide_verificare',
    'lista_neincepute', 'forteaza_verificare',
    'lista_conturi', 'restabileste_biometrie'
  ));

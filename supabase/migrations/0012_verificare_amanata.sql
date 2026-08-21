-- =============================================================================
-- Libra — buletinul devine optional la inregistrare
--
-- Selfie-ul ramane obligatoriu (e refolosit la login biometric si e reperul
-- fata de care se compara buletinul, oricand ar fi trimis). Buletinul poate
-- lipsi la inregistrare si fi trimis mai tarziu, din aplicatie — verificarea
-- (OCR + comparare fete) se face atunci, contra selfie-ului retinut aici.
-- =============================================================================

alter table public.profiles
  add column if not exists selfie_referinta_path text;

comment on column public.profiles.selfie_referinta_path is
  'Calea selfie-ului din bucket-ul selfie-uri, retinuta la inregistrare (sau la
   ultima verificare) ca sa poata fi refolosita cand utilizatorul trimite
   buletinul mai tarziu. Nu e sursa pentru login biometric — aceea ramane
   ultimul selfie dintr-o verificare cu status=verified (identity_verifications).';

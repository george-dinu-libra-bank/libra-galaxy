-- =============================================================================
-- Libra — nivel de incredere pe mesajele asistentului
--
-- Aditiva la 0004/0005. Utilizatorul nu mai vede in chat sursa exacta a unui
-- raspuns (nume de tool, id de document) — doar un nivel de incredere calculat
-- determinist din rezultatele tool-urilor / scorul de regasire (ai/agents/base.py),
-- niciodata inventat de model. `citari` ramane neschimbata, pentru audit.
-- =============================================================================

alter table public.ai_messages
  add column if not exists nivel_incredere text;

alter table public.ai_messages
  add constraint ai_messages_nivel_incredere_check
  check (nivel_incredere is null or nivel_incredere in ('ridicat', 'mediu', 'scazut'));

comment on column public.ai_messages.nivel_incredere is 'Incredere determinista (ridicat/mediu/scazut), afisata in loc de sursa exacta. Null pentru mesajele utilizatorului sau raspunsuri fara grounding (ex. compliance_kyc).';

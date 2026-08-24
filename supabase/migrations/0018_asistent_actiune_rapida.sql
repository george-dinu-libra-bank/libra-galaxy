-- =============================================================================
-- Libra — actiune rapida atasata unui raspuns determinist al asistentului
--
-- Aditiva la 0004_ai_asistent.sql. Spre deosebire de ai_message_attachments
-- (0005), datele astea nu sunt sensibile si nu expira ca un URL semnat — se
-- pot stoca direct pe mesaj, fara tabel separat.
-- =============================================================================

alter table public.ai_messages
  add column if not exists actiune_rapida jsonb;

comment on column public.ai_messages.actiune_rapida is
  'Actiune rapida atasata unui raspuns determinist (ex. card cont + link spre /transfer) — vezi orchestrator.py::_handle_transfer_request.';

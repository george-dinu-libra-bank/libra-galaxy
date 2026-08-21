-- =============================================================================
-- Libra — export PDF de tranzactii, generat de aplicatie (nu incarcat de user)
--
-- Aditiva la 0005_ai_asistent_atasamente_voce.sql. Reutilizeaza tabela
-- ai_message_attachments (deja are id_message/tip/storage_path/nume_fisier),
-- doar cu o coloana noua care distinge intrare (incarcat de user) de iesire
-- (generat de backend) — simetric cu fluxul existent, fara tabel nou.
-- =============================================================================

alter table public.ai_message_attachments
  add column if not exists directie text not null default 'intrare';

alter table public.ai_message_attachments
  add constraint ai_message_attachments_directie_check check (directie in ('intrare', 'iesire'));

comment on column public.ai_message_attachments.directie is 'intrare = incarcat de utilizator, iesire = generat de backend (ex. export PDF de tranzactii).';

-- -----------------------------------------------------------------------------
-- Storage: bucket privat separat de asistent-atasamente — acela e pentru input
-- utilizator, cu whitelist de content-type gandit pentru asta; acesta e mereu
-- PDF, generat determinist de backend (services/transaction_export_service.py).
-- -----------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'asistent-exporturi', 'asistent-exporturi', false, 10485760,
  array['application/pdf']
)
on conflict (id) do nothing;

drop policy if exists "exporturi storage: select propriu" on storage.objects;
create policy "exporturi storage: select propriu"
  on storage.objects for select to authenticated
  using (bucket_id = 'asistent-exporturi' and (storage.foldername(name))[1] = auth.uid()::text);

-- Upload-ul se face din backend cu service_role, dupa generarea PDF-ului —
-- nu exista politica de insert pentru authenticated.

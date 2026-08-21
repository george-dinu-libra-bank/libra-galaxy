-- =============================================================================
-- Libra — atasamente (PDF/poze) si canal vocal pentru asistent
--
-- Aditiva la 0004_ai_asistent.sql. Fisierele stau in Supabase Storage
-- (bucket privat), randul din ai_message_attachments e doar metadata +
-- textul extras determinist din PDF (pentru poze, continutul e trimis direct
-- modelului de chat, nu se stocheaza text derivat).
-- =============================================================================

alter table public.ai_messages
  add column if not exists canal text not null default 'text';

alter table public.ai_messages
  add constraint ai_messages_canal_check check (canal in ('text', 'voce'));

comment on column public.ai_messages.canal is 'Canalul prin care a intrat/iesit mesajul — text sau voce (docs/AI_ARCHITECTURE.md #9).';

create table if not exists public.ai_message_attachments (
  id             uuid primary key default gen_random_uuid(),
  id_message     uuid references public.ai_messages (id) on delete cascade,
  id_user        uuid        not null references public.profiles (id) on delete cascade,
  tip            text        not null,
  nume_fisier    text        not null,
  storage_path   text        not null,
  content_type   text        not null,
  marime_octeti  integer     not null,
  text_extras    text,
  creat_la       timestamptz not null default now(),

  constraint ai_message_attachments_tip_check check (tip in ('pdf', 'imagine')),
  constraint ai_message_attachments_marime_check check (marime_octeti > 0)
);

comment on table public.ai_message_attachments is 'PDF-uri si poze atasate unui mesaj. id_message e null pana cand mesajul e persistat (upload precede trimiterea).';

create index if not exists ai_message_attachments_id_user_idx on public.ai_message_attachments (id_user);
create index if not exists ai_message_attachments_id_message_idx on public.ai_message_attachments (id_message);

alter table public.ai_message_attachments enable row level security;

drop policy if exists "atasamente proprii: select" on public.ai_message_attachments;
create policy "atasamente proprii: select"
  on public.ai_message_attachments for select to authenticated
  using (auth.uid() = id_user);

grant select on public.ai_message_attachments to authenticated;

-- -----------------------------------------------------------------------------
-- Storage: bucket privat, un folder per utilizator (auth.uid()/...), la fel ca
-- pattern-ul de izolare din restul schemei — filtrul e primul segment din path.
-- -----------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'asistent-atasamente', 'asistent-atasamente', false, 10485760,
  array['application/pdf', 'image/png', 'image/jpeg', 'image/webp']
)
on conflict (id) do nothing;

drop policy if exists "atasamente storage: select propriu" on storage.objects;
create policy "atasamente storage: select propriu"
  on storage.objects for select to authenticated
  using (bucket_id = 'asistent-atasamente' and (storage.foldername(name))[1] = auth.uid()::text);

-- Upload-ul se face din backend cu service_role (dupa validare de tip/marime),
-- nu exista politica de insert pentru authenticated.

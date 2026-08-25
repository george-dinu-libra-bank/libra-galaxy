-- Mesajul analistului ajunge la client fara reincarcare de pagina.
--
-- Firul se improspata pana acum doar ca **efect colateral** al unei miscari de
-- bani: `use-canal-utilizator` face `router.refresh()` global la orice
-- tranzactie, deci un mesaj aparea daca omul primea intre timp un transfer.
-- Altfel statea acolo nevazut.
--
-- Se refoloseste canalul privat care exista deja (`user:<id>`) si helperul
-- `anunta_utilizator` din 0000, nu `postgres_changes`: `credit_mesaje` are RLS
-- activ si zero politici (doar service_role), deci un abonament direct la
-- tabela n-ar livra nimic unui client — si nici n-ar trebui.

create or replace function public.credit_mesaj_anunta()
returns trigger
language plpgsql
security definer
set search_path to ''
as $$
declare
  v_id_user uuid;
begin
  -- Doar mesajele bancii. Ale clientului si cele de sistem sunt produse de
  -- fapta lui: nu are ce sa-l anunte pe el despre ce tocmai a facut.
  if new.autor <> 'analist' then
    return new;
  end if;

  select c.id_user into v_id_user
  from public.credit_cereri c
  where c.id = new.id_cerere;

  if v_id_user is null then
    return new;
  end if;

  perform public.anunta_utilizator(
    v_id_user,
    'mesaj_credit',
    jsonb_build_object('id_cerere', new.id_cerere, 'id_mesaj', new.id)
  );

  return new;
end;
$$;

drop trigger if exists credit_mesaje_anunta on public.credit_mesaje;

create trigger credit_mesaje_anunta
  after insert on public.credit_mesaje
  for each row
  execute function public.credit_mesaj_anunta();

import type { StilCard } from "@/lib/data/carduri";
import { ETICHETE_STIL_CARD } from "@/lib/stil-card";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

/**
 * Datele ecranului de transfer, luate din Supabase:
 *  - „contul sursa" e un card propriu (public.carduri, cu sold_curent);
 *  - beneficiarii sunt profiluri reale (public.profiles), identificate prin IBAN.
 * Nu exista conturi IBAN separate in schema — vezi supabase/migrations.
 */

export const BANCA_INTERNA = "Libra Bank";
export const VALUTA_IMPLICITA = "RON";

export type ContSursa = {
  id: string;
  nume: string;
  numarMascat: string;
  sold: number;
  valuta: string;
  blocat: boolean;
};

export type BeneficiarTransfer = {
  id: string;
  nume: string;
  iban: string;
  banca: string;
};

/** Cardurile din care utilizatorul curent poate trimite bani. */
export async function obtineConturiTransfer(): Promise<ContSursa[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("carduri")
    .select("id, numar_card, card_style, sold_curent, is_blocked, creat_la")
    .eq("id_user", user.id)
    .order("creat_la", { ascending: true });

  if (error) throw error;

  return (data ?? []).map((card) => ({
    id: card.id as string,
    nume: `Card ${ETICHETE_STIL_CARD[card.card_style as StilCard]}`,
    numarMascat: `•••• ${(card.numar_card as string).slice(-4)}`,
    sold: Number(card.sold_curent),
    valuta: VALUTA_IMPLICITA,
    blocat: card.is_blocked as boolean,
  }));
}

/**
 * Beneficiarii recenti — profilurile cu care utilizatorul a mai schimbat bani,
 * cele mai recente primele. Profilurile altor utilizatori nu se pot citi cu
 * cheia anon (RLS), asa ca lista se compune cu clientul de service_role, dar
 * doar pentru id-urile care apar in propriile tranzactii.
 */
export async function obtineBeneficiariRecenti(): Promise<BeneficiarTransfer[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("tranzactii")
    .select("id_user_send, id_user_recieve, creat_la")
    .or(`id_user_send.eq.${user.id},id_user_recieve.eq.${user.id}`)
    .order("creat_la", { ascending: false })
    .limit(100);

  if (error) throw error;

  // Ordinea de aici da ordinea din lista: contrapartida cea mai recenta prima.
  const idUri: string[] = [];

  for (const tranzactie of data ?? []) {
    const contrapartida =
      tranzactie.id_user_send === user.id
        ? (tranzactie.id_user_recieve as string | null)
        : (tranzactie.id_user_send as string | null);

    if (contrapartida && contrapartida !== user.id && !idUri.includes(contrapartida)) {
      idUri.push(contrapartida);
    }
  }

  if (idUri.length === 0) return [];

  const supabaseAdmin = createAdminClient();

  const { data: profiluri, error: eroareProfiluri } = await supabaseAdmin
    .from("profiles")
    .select("id, nume, iban_cont")
    .in("id", idUri);

  if (eroareProfiluri) throw eroareProfiluri;

  const dupaId = new Map(
    (profiluri ?? []).map((profil) => [
      profil.id as string,
      {
        id: profil.id as string,
        nume: profil.nume as string,
        iban: profil.iban_cont as string,
        banca: BANCA_INTERNA,
      },
    ]),
  );

  return idUri.map((id) => dupaId.get(id)).filter((b): b is BeneficiarTransfer => Boolean(b));
}

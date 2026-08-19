import { createClient } from "@/lib/supabase/server";

export type StilCard = "standard" | "silver" | "gold";

export type CardAfisat = {
  id: string;
  stil: StilCard;
  numarMascat: string;
  dataExpirare: string;
  /** Soldul contului — toate cardurile dau acces la aceiasi bani. */
  soldCurent: number;
  blocat: boolean;
};

/**
 * Cardurile utilizatorului curent. Un profil nou nu are niciun card.
 * Banii nu stau pe card, ci pe cont (public.profiles.sold_curent), asa ca
 * fiecare card afiseaza soldul contului — vezi 0004_core_banking.sql.
 */
export async function obtineCarduriUtilizator(): Promise<CardAfisat[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const [{ data, error }, { data: profil, error: eroareProfil }] = await Promise.all([
    supabase
      .from("carduri")
      .select("id, numar_card, data_expirare, card_style, is_blocked, creat_la")
      .eq("id_user", user.id)
      .order("creat_la", { ascending: true }),
    supabase.from("profiles").select("sold_curent").eq("id", user.id).maybeSingle(),
  ]);

  if (error) throw error;
  if (eroareProfil) throw eroareProfil;

  const sold = Number(profil?.sold_curent ?? 0);

  return (data ?? []).map((card) => ({
    id: card.id as string,
    stil: card.card_style as StilCard,
    numarMascat: `•••• •••• •••• ${(card.numar_card as string).slice(-4)}`,
    dataExpirare: card.data_expirare as string,
    soldCurent: sold,
    blocat: card.is_blocked as boolean,
  }));
}

import { obtineConturiUtilizator, totalSold } from "@/lib/data/conturi";
import { createClient } from "@/lib/supabase/server";

export type StilCard = "standard" | "silver" | "gold";

export type CardAfisat = {
  id: string;
  stil: StilCard;
  numarMascat: string;
  dataExpirare: string;
  /** Totalul din conturi — cardul e instrument, nu portofel. */
  soldCurent: number;
  blocat: boolean;
};

/**
 * Cardurile utilizatorului curent. Un profil nou nu are niciun card.
 * Banii nu stau pe card, ci pe conturile bancare, asa ca fiecare card afiseaza
 * totalul din conturi — vezi 0007_conturi_bancare.sql.
 */
export async function obtineCarduriUtilizator(): Promise<CardAfisat[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const [{ data, error }, conturi] = await Promise.all([
    supabase
      .from("carduri")
      .select("id, numar_card, data_expirare, card_style, is_blocked, creat_la")
      .eq("id_user", user.id)
      .order("creat_la", { ascending: true }),
    obtineConturiUtilizator(),
  ]);

  if (error) throw error;

  const sold = totalSold(conturi);

  return (data ?? []).map((card) => ({
    id: card.id as string,
    stil: card.card_style as StilCard,
    numarMascat: `•••• •••• •••• ${(card.numar_card as string).slice(-4)}`,
    dataExpirare: card.data_expirare as string,
    soldCurent: sold,
    blocat: card.is_blocked as boolean,
  }));
}

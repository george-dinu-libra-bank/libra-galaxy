import { createClient } from "@/lib/supabase/server";

export type StilCard = "standard" | "silver" | "gold";

export type CardAfisat = {
  id: string;
  stil: StilCard;
  numarMascat: string;
  dataExpirare: string;
  soldCurent: number;
  blocat: boolean;
};

/** Cardurile utilizatorului curent. Un profil nou nu are niciun card. */
export async function obtineCarduriUtilizator(): Promise<CardAfisat[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("carduri")
    .select("id, numar_card, data_expirare, card_style, sold_curent, is_blocked, creat_la")
    .eq("id_user", user.id)
    .order("creat_la", { ascending: true });

  if (error) throw error;

  return (data ?? []).map((card) => ({
    id: card.id as string,
    stil: card.card_style as StilCard,
    numarMascat: `•••• •••• •••• ${(card.numar_card as string).slice(-4)}`,
    dataExpirare: card.data_expirare as string,
    soldCurent: Number(card.sold_curent),
    blocat: card.is_blocked as boolean,
  }));
}

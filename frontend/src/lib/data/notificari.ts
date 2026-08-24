import "server-only";

import { createClient } from "@/lib/supabase/server";

export type Notificare = {
  id: string;
  titlu: string;
  mesaj: string;
  tip: "info" | "atentionare" | "blocare" | "deblocare";
  citita_la: string | null;
  creat_la: string;
};

/**
 * Mesajele bancii pentru clientul curent.
 *
 * Se citesc cu sesiunea lui, nu cu cheia privilegiata: politica de pe
 * `notificari` lasa fiecare om sa vada doar ce e al lui, deci baza de date
 * ramane bariera, nu codul de aici.
 */
export async function obtineNotificari(limita = 20): Promise<Notificare[]> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return [];

  const { data, error } = await supabase
    .from("notificari")
    .select("id,titlu,mesaj,tip,citita_la,creat_la")
    .eq("id_utilizator", user.id)
    .order("creat_la", { ascending: false })
    .limit(limita);

  if (error || !data) return [];
  return data as Notificare[];
}

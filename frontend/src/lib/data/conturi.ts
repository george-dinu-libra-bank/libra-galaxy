import { createClient } from "@/lib/supabase/server";

export type ContBancar = {
  id: string;
  nume: string;
  iban: string;
  /** Ultimele 4 cifre, pentru liste: „•••• 4821". */
  ibanMascat: string;
  sold: number;
  /** RON, EUR, USD, GBP sau CHF. Creditele se vireaza numai in conturi RON. */
  valuta: string;
  creatLa: string;
};

/**
 * Conturile bancare ale utilizatorului curent, cel mai vechi primul — primul
 * din lista e contul principal, cel deschis la inregistrare.
 *
 * Banii stau aici, nu pe profil si nu pe card (0007_conturi_bancare.sql).
 */
export async function obtineConturiUtilizator(): Promise<ContBancar[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("conturi_bancare")
    .select("id, nume, iban, sold, valuta, creat_la")
    .eq("id_user", user.id)
    .order("creat_la", { ascending: true });

  if (error) throw error;

  return (data ?? []).map((cont) => ({
    id: cont.id as string,
    nume: cont.nume as string,
    iban: cont.iban as string,
    ibanMascat: `•••• ${(cont.iban as string).slice(-4)}`,
    sold: Number(cont.sold),
    valuta: (cont.valuta as string) ?? "RON",
    creatLa: cont.creat_la as string,
  }));
}

/**
 * Totalul din toate conturile. Se aduna pe server, ca sa nu depinda cifra mare
 * de pe dashboard de ce apuca sa randeze clientul.
 */
export function totalSold(conturi: ContBancar[]) {
  // Soldurile sunt numeric(14,2); adunarea in bani evita resturile din virgula
  // mobila (0.1 + 0.2 = 0.30000000000000004).
  const bani = conturi.reduce((total, cont) => total + Math.round(cont.sold * 100), 0);
  return bani / 100;
}

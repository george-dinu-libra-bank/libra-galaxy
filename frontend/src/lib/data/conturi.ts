import { createClient } from "@/lib/supabase/server";
import type { Valuta } from "@/lib/valute";

export type ContBancar = {
  id: string;
  nume: string;
  iban: string;
  /** Ultimele 4 cifre, pentru liste: „•••• 4821". */
  ibanMascat: string;
  sold: number;
  /** Valuta in care e tinut soldul (0013_schimb_valutar.sql). */
  valuta: Valuta;
  /** Oprit de banca: din el nu mai pot pleca bani. */
  blocatDeBanca: boolean;
  creatLa: string;
};

/**
 * Conturile bancare ale utilizatorului curent, cel mai vechi primul — primul
 * din lista e contul principal, cel deschis la inregistrare.
 *
 * Banii stau aici, nu pe profil si nu pe card (tabela conturi_bancare (creata direct in Supabase, fara migrare in repo)).
 */
export async function obtineConturiUtilizator(): Promise<ContBancar[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("conturi_bancare")
    .select("id, nume, iban, sold, valuta, blocat_administrativ, creat_la")
    .eq("id_user", user.id)
    .order("creat_la", { ascending: true });

  if (error) throw error;

  return (data ?? []).map((cont) => ({
    id: cont.id as string,
    nume: cont.nume as string,
    iban: cont.iban as string,
    ibanMascat: `•••• ${(cont.iban as string).slice(-4)}`,
    sold: Number(cont.sold),
    valuta: (cont.valuta as Valuta) ?? "RON",
    blocatDeBanca: (cont.blocat_administrativ as boolean) ?? false,
    creatLa: cont.creat_la as string,
  }));
}

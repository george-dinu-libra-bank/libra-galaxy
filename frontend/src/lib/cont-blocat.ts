import "server-only";

import { createAdminClient } from "@/lib/supabase/admin";

export const MESAJ_CONT_BLOCAT =
  "Contul tău este blocat temporar. Verifică mesajele din aplicație sau contactează banca.";

/**
 * Daca administratorul a blocat cardurile acestui om.
 *
 * Verificarea sta in aplicatie, nu in functiile de baza de date care mai bine
 * ar fi facut-o (`core_banking`, `core_banking_groups`, operatiunile de
 * credit). Acelea exista deja si nu le rescriem, asa ca fiecare drum prin care
 * pot pleca bani trebuie sa cheme functia asta inainte.
 *
 * Limita, spusa pe fata: acopera drumurile prin aplicatie — singurele folosite
 * de interfata — dar nu si pe cineva care ar chema RPC-urile direct cu tokenul
 * lui. Platile cu cardul sunt singurele oprite chiar in baza de date, fiindca
 * `creeaza_plata` si `aproba_plata` verifica ele insele `carduri.is_blocked`.
 *
 * Un singur loc, ca sa nu apara al doilea drum neaparat cand cineva adauga
 * maine inca o cale prin care ies bani.
 */
export async function contEsteBlocat(idUtilizator: string): Promise<boolean> {
  const supabaseAdmin = createAdminClient();

  const { count, error } = await supabaseAdmin
    .from("carduri")
    .select("id", { count: "exact", head: true })
    .eq("id_user", idUtilizator)
    .eq("is_blocked", true);

  // La eroare lasam sa treaca: o interogare cazuta nu trebuie sa blocheze toti
  // clientii bancii. Blocarea reala a platilor cu cardul ramane oricum in baza.
  if (error) return false;

  return (count ?? 0) > 0;
}

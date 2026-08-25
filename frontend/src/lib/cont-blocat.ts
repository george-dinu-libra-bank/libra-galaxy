import "server-only";

import { createAdminClient } from "@/lib/supabase/admin";

export const MESAJ_CONT_BLOCAT =
  "Contul tău este blocat temporar. Verifică mesajele din aplicație sau contactează banca.";

/**
 * Daca administratorul a blocat vreun cont al acestui om.
 *
 * Se uita la `conturi_bancare.blocat_administrativ`, nu la carduri. Inainte
 * numara cardurile cu `is_blocked`, ceea ce parea acelasi lucru dar nu era:
 * `is_blocked` e si butonul prin care CLIENTUL isi blocheaza un card pierdut,
 * asa ca un om care isi bloca propriul card ramanea si fara transferuri. Cele
 * doua sunt acum steaguri diferite, cu intelesuri diferite.
 *
 * Verificarea de aici e o comoditate, nu bariera: din 0030, un trigger pe
 * `conturi_bancare` refuza orice scadere de sold pe un cont blocat, deci
 * blocarea tine si daca cineva cheama RPC-ul direct, ocolind aplicatia.
 * Rostul acestei functii e sa dea un mesaj omenesc inainte, in loc sa lase
 * utilizatorul sa se loveasca de o eroare de baza de date.
 */
export async function contEsteBlocat(idUtilizator: string): Promise<boolean> {
  const supabaseAdmin = createAdminClient();

  const { count, error } = await supabaseAdmin
    .from("conturi_bancare")
    .select("id", { count: "exact", head: true })
    .eq("id_user", idUtilizator)
    .eq("blocat_administrativ", true);

  // La eroare lasam sa treaca: o interogare cazuta nu trebuie sa blocheze toti
  // clientii bancii, iar bariera adevarata e oricum in baza de date.
  if (error) return false;

  return (count ?? 0) > 0;
}

import { createClient } from "@/lib/supabase/server";
import { converteste, type Curs, type Valuta } from "@/lib/valute";

export type ContBancar = {
  id: string;
  nume: string;
  iban: string;
  /** Ultimele 4 cifre, pentru liste: „•••• 4821". */
  ibanMascat: string;
  sold: number;
  /** Valuta in care e tinut soldul (0013_schimb_valutar.sql). */
  valuta: Valuta;
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
    valuta: (cont.valuta as Valuta) ?? "RON",
    creatLa: cont.creat_la as string,
  }));
}

/**
 * Totalul din toate conturile, exprimat in RON.
 *
 * De cand conturile pot fi in valute diferite (0013_schimb_valutar.sql), o
 * simpla adunare a soldurilor ar da o cifra fara sens — 100 EUR plus 100 RON nu
 * fac 200 din nimic. Fiecare cont se aduce intai la RON, la cursul BNR.
 *
 * Un cont a carui valuta n-are curs (BNR inca n-a raspuns niciodata) se lasa
 * afara din total: mai bine o cifra mai mica si corecta decat una inventata.
 */
export function totalSold(conturi: ContBancar[], cursuri: Curs[]) {
  // Soldurile sunt numeric(14,2); adunarea in bani evita resturile din virgula
  // mobila (0.1 + 0.2 = 0.30000000000000004).
  const bani = conturi.reduce((total, cont) => {
    const inLei = converteste(cont.sold, cont.valuta, "RON", cursuri);
    return inLei === null ? total : total + Math.round(inLei * 100);
  }, 0);

  return bani / 100;
}

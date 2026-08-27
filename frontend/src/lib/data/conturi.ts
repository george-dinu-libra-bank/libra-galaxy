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
  /**
   * Contul deschis odata cu profilul, cel al carui IBAN sta in
   * `profiles.iban_cont`.
   *
   * NU „primul din lista": ordinea dupa `creat_la` da acelasi rezultat azi si
   * altul in ziua in care cineva sterge un cont vechi. `iban_cont` e si
   * identificatorul pe care il foloseste `consolideaza_conturile` (migratia
   * 0037) ca sa decida unde se strang banii la inchiderea relatiei — daca
   * interfata ar arata alt cont decat cel in care banca muta banii, ar fi o
   * minciuna cu consecinte.
   */
  estePrincipal: boolean;
  /**
   * Cererea de inchidere inca nedecisa, daca exista. Contul functioneaza normal
   * cat timp e in analiza — se schimba doar ce scrie in meniul lui.
   */
  cerereInchidere: { id: string; creatLa: string } | null;
  creatLa: string;
};

/**
 * Conturile bancare ale utilizatorului curent, cel mai vechi primul.
 *
 * Contul principal se marcheaza dupa `profiles.iban_cont`, nu dupa pozitia in
 * lista (vezi `estePrincipal`).
 *
 * Banii stau aici, nu pe profil si nu pe card (tabela conturi_bancare (creata direct in Supabase, fara migrare in repo)).
 */
export async function obtineConturiUtilizator(): Promise<ContBancar[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  // Un singur rand, o singura coloana — IBAN-ul contului principal. Se citeste
  // aici, nu se cere apelantului, ca marcajul sa fie corect oriunde se folosesc
  // conturile, nu doar pe dashboard.
  const { data: profil } = await supabase
    .from("profiles")
    .select("iban_cont")
    .eq("id", user.id)
    .single();

  const ibanPrincipal = (profil?.iban_cont as string | null) ?? null;

  const { data, error } = await supabase
    .from("conturi_bancare")
    .select("id, nume, iban, sold, valuta, blocat_administrativ, creat_la")
    .eq("id_user", user.id)
    // Conturile inchise (0040) raman in baza, ca istoricul sa le pastreze numele,
    // dar n-au ce cauta in liste: nu mai pot primi si nu mai pot trimite bani.
    .is("inchis_la", null)
    .order("creat_la", { ascending: true });

  if (error) throw error;

  // Cererile de inchidere inca nedecise, ca meniul contului sa arate „in analiza"
  // in loc sa ofere din nou un buton care ar fi respins de indexul unic.
  const { data: cereri } = await supabase
    .from("cereri_inchidere_cont")
    .select("id, id_cont, creat_la")
    .eq("id_utilizator", user.id)
    .eq("status", "in_asteptare");

  const cereriPeCont = new Map<string, { id: string; creatLa: string }>();
  for (const cerere of cereri ?? []) {
    cereriPeCont.set(cerere.id_cont as string, {
      id: cerere.id as string,
      creatLa: cerere.creat_la as string,
    });
  }

  return (data ?? []).map((cont) => ({
    id: cont.id as string,
    nume: cont.nume as string,
    iban: cont.iban as string,
    ibanMascat: `•••• ${(cont.iban as string).slice(-4)}`,
    sold: Number(cont.sold),
    valuta: (cont.valuta as Valuta) ?? "RON",
    blocatDeBanca: (cont.blocat_administrativ as boolean) ?? false,
    estePrincipal: ibanPrincipal !== null && cont.iban === ibanPrincipal,
    cerereInchidere: cereriPeCont.get(cont.id as string) ?? null,
    creatLa: cont.creat_la as string,
  }));
}

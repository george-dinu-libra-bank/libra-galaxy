"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { invalideazaCuvinteSensibile } from "@/lib/cuvinte-sensibile";
import { createAdminClient } from "@/lib/supabase/admin";

export type RezultatSalvareCuvinte = { eroare?: string; cuvinte?: string[] };
export type RezultatDecizieSemnalare = { eroare?: string; status?: string };

/** Cat de lung poate fi un cuvant sau o expresie din lista. */
const LUNGIME_MAXIMA = 60;
/** Cate intrari incap in lista. Scanarea e liniara in numarul lor. */
const MAXIM_CUVINTE = 500;

/**
 * Imparte textul din caseta in cuvinte: cate unul pe linie sau despartite prin
 * virgula. Expresiile („spalare de bani") raman intregi — spatiul din interior
 * nu e separator.
 *
 * Nu se exporta: intr-un fisier „use server" pot iesi doar functii async.
 */
function despartCuvinte(text: string): string[] {
  const vazute = new Set<string>();
  const cuvinte: string[] = [];

  for (const bucata of text.split(/[\n,;]+/)) {
    const cuvant = bucata.trim().replace(/\s+/g, " ").slice(0, LUNGIME_MAXIMA);
    if (!cuvant) continue;

    // Duplicatele se taie fara sa tina cont de litere mari: potrivirea e oricum
    // insensibila la ele, deci doua variante ar face aceeasi munca de doua ori.
    const cheie = cuvant.toLowerCase();
    if (vazute.has(cheie)) continue;

    vazute.add(cheie);
    cuvinte.push(cuvant);
  }

  return cuvinte.slice(0, MAXIM_CUVINTE);
}

/**
 * Salveaza lista de cuvinte sensibile, inlocuind-o pe cea veche.
 *
 * Tabela are un singur rand (index unic pe o expresie constanta, 0043), deci
 * salvarea inseamna „update daca exista, altfel insert". Dupa scriere, cache-ul
 * scanerului e aruncat, ca urmatorul transfer sa foloseasca lista noua fara sa
 * astepte expirarea.
 */
export async function salveazaCuvinteSensibile(
  text: string,
): Promise<RezultatSalvareCuvinte> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  const cuvinte = despartCuvinte(text);
  const supabaseAdmin = createAdminClient();

  const { data: existent, error: eroareCitire } = await supabaseAdmin
    .from("sensitive_words")
    .select("id")
    .limit(1)
    .maybeSingle();

  if (eroareCitire) {
    console.error("ERROR salveazaCuvinteSensibile (citire):", eroareCitire);
    return { eroare: "Nu am putut citi lista curentă. Încearcă din nou." };
  }

  const rand = {
    cuvinte,
    actualizat_la: new Date().toISOString(),
    actualizat_de: admin.id,
  };

  const { error } = existent
    ? await supabaseAdmin.from("sensitive_words").update(rand).eq("id", existent.id)
    : await supabaseAdmin.from("sensitive_words").insert(rand);

  if (error) {
    console.error("ERROR salveazaCuvinteSensibile:", error);
    return { eroare: "Nu am putut salva lista. Încearcă din nou." };
  }

  invalideazaCuvinteSensibile();
  revalidatePath("/admin/securitate");

  return { cuvinte };
}

/**
 * Mesajele pentru codurile ridicate de `decide_transfer_semnalat` (0043).
 * Aceeasi conventie ca la transfer: codul in `message`, textul lung in `detail`.
 */
const MESAJE_DECIZIE: Record<string, string> = {
  TRANZACTIE_INEXISTENTA: "Transferul nu mai există.",
  DEJA_DECISA: "Transferul a fost deja rezolvat, poate de un alt administrator.",
  DECIZIE_INVALIDA: "Decizie necunoscută.",
  CONT_BENEFICIAR_INEXISTENT:
    "Contul beneficiarului nu mai există; transferul poate fi doar anulat.",
  CONT_SURSA_INEXISTENT: "Contul din care au plecat banii nu mai există.",
  GRUP_INEXISTENT: "Grupul din care au plecat banii nu mai există.",
  SUMA_PREA_MICA: "Suma e prea mică pentru a ajunge în valuta beneficiarului.",
};

/**
 * Eliberarea sau anularea unui transfer semnalat.
 *
 * Toata miscarea de bani se face in baza, intr-o singura tranzactie; aici raman
 * verificarea de rol si traducerea codurilor.
 */
export async function decideTranzactieSemnalata(
  idTranzactie: string,
  decizie: "accepta" | "anuleaza",
): Promise<RezultatDecizieSemnalare> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  const supabaseAdmin = createAdminClient();

  const { data, error } = await supabaseAdmin.rpc("decide_transfer_semnalat", {
    p_id: idTranzactie,
    p_decizie: decizie,
    p_id_admin: admin.id,
  });

  if (error) {
    const mesaj = MESAJE_DECIZIE[error.message];
    if (!mesaj) console.error("ERROR decideTranzactieSemnalata:", error);
    return { eroare: mesaj ?? "Nu am putut salva decizia. Încearcă din nou." };
  }

  revalidatePath("/admin/tranzactii-suspecte");
  // Soldurile si istoricul celor doi implicati s-au schimbat.
  revalidatePath("/dashboard");
  revalidatePath("/istoric");
  revalidatePath("/grupuri");

  return { status: (data as { status?: string } | null)?.status };
}

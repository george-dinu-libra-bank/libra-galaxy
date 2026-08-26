"use server";

import { revalidatePath } from "next/cache";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

export type RezultatCont = { eroare?: string };

/**
 * Cate conturi poate avea un om — destul pentru orice folosire reala.
 *
 * Acelasi plafon e hardcodat si in `schimba_valuta_suma`
 * (supabase/migrations/0019_schimb_valutar_suma.sql), care deschide conturi
 * automat la schimb valutar. Cele doua se sincronizeaza manual: daca schimbi
 * numarul aici, schimba-l si acolo.
 */
const MAX_CONTURI = 10;

/**
 * Deschide un cont bancar nou, cu IBAN generat in baza de date
 * (public.genereaza_iban, tabela conturi_bancare (creata direct in Supabase, fara migrare in repo)).
 *
 * Tabela nu are politici de INSERT tocmai ca nimeni sa nu-si poata crea un rand
 * cu sold pus de mana, deci inserarea merge cu service_role — dar id_user vine
 * mereu din sesiune, nu din formular, si soldul porneste de la 0.
 */
export async function deschideCont(numeBrut: string): Promise<RezultatCont> {
  const supabase = await createClient();
  const supabaseAdmin = createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const nume = numeBrut.trim();

  if (nume.length < 2 || nume.length > 60) {
    return { eroare: "Numele contului trebuie să aibă între 2 și 60 de caractere." };
  }

  const { count, error: eroareNumar } = await supabaseAdmin
    .from("conturi_bancare")
    .select("id", { count: "exact", head: true })
    .eq("id_user", user.id);

  if (eroareNumar) {
    console.error("ERROR deschideCont (numarare):", eroareNumar);
    return { eroare: "Nu am putut deschide contul. Încearcă din nou." };
  }

  if ((count ?? 0) >= MAX_CONTURI) {
    return { eroare: `Poți avea cel mult ${MAX_CONTURI} conturi.` };
  }

  const { data: iban, error: eroareIban } = await supabaseAdmin.rpc("genereaza_iban");

  if (eroareIban || !iban) {
    console.error("ERROR deschideCont (iban):", eroareIban);
    return { eroare: "Nu am putut genera IBAN-ul. Încearcă din nou." };
  }

  const { error } = await supabaseAdmin
    .from("conturi_bancare")
    .insert({ id_user: user.id, nume, iban });

  if (error) {
    console.error("ERROR deschideCont:", error);
    return { eroare: "Nu am putut deschide contul. Încearcă din nou." };
  }

  revalidatePath("/dashboard");
  revalidatePath("/transfer");

  return {};
}

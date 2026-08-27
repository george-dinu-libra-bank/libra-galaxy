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

/** Aceleasi limite la deschidere si la redenumire — o singura definitie. */
function validNume(nume: string): string | null {
  if (nume.length < 2 || nume.length > 60) {
    return "Numele contului trebuie să aibă între 2 și 60 de caractere.";
  }
  return null;
}

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
  const problema = validNume(nume);
  if (problema) return { eroare: problema };

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


/**
 * Redenumeste un cont bancar.
 *
 * Fara cerere la banca: numele contului e o eticheta pentru ochii clientului, nu
 * un element de identificare. IBAN-ul, soldul si istoricul raman neatinse, iar
 * numele vechi ramane in tranzactiile deja scrise doar in masura in care acelea
 * il citesc la afisare — deci se actualizeaza peste tot deodata, ceea ce e si
 * comportamentul asteptat („am scris gresit numele, l-am corectat").
 *
 * Scrierea merge cu service-role, ca la `deschideCont`, si din acelasi motiv:
 * `conturi_bancare` NU are politica de UPDATE pentru „authenticated" — tocmai ca
 * nimeni sa nu-si poata scrie soldul de mana din browser. Verificat in baza
 * inainte de a scrie codul asta: un update cu clientul utilizatorului ar fi
 * intors tacit zero randuri, si butonul ar fi parut ca nu face nimic.
 *
 * Proprietatea se impune aici, in filtru: `.eq("id_user", user.id)` cu id-ul din
 * sesiune, niciodata din formular. Se schimba doar `nume`.
 */
export async function redenumesteCont(
  idCont: string,
  numeBrut: string,
): Promise<RezultatCont> {
  const supabase = await createClient();
  const supabaseAdmin = createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie să fii autentificat." };

  const nume = numeBrut.trim();
  const problema = validNume(nume);
  if (problema) return { eroare: problema };

  const { data, error } = await supabaseAdmin
    .from("conturi_bancare")
    .update({ nume })
    .eq("id", idCont)
    .eq("id_user", user.id)
    .is("inchis_la", null)
    .select("id");

  if (error) {
    console.error("ERROR redenumesteCont:", error);
    return { eroare: "Nu am putut redenumi contul. Încearcă din nou." };
  }

  if (!data || data.length === 0) {
    return { eroare: "Contul nu mai există sau a fost închis." };
  }

  revalidatePath("/dashboard");
  revalidatePath("/transfer");
  revalidatePath("/carduri");

  return {};
}

/**
 * Muta titlul de „cont principal" pe alt cont al aceluiasi om.
 *
 * Contul principal e definit de `profiles.iban_cont` — nu de o coloana pe cont si
 * nu de pozitia in lista. Schimbarea inseamna deci un singur update pe profil.
 *
 * Fara cerere la banca: alegerea nu misca niciun ban si nu inchide nimic. Are
 * insa doua urmari reale, si de aceea ecranul le scrie inainte de apasare:
 * IBAN-ul principal e cel pe care il dai mai departe, si e contul in care se
 * strang banii la inchiderea relatiei (`consolideaza_conturile`, 0037). Tot el
 * devine contul care NU se mai poate inchide, iar cel de dinainte se elibereaza.
 *
 * Update-ul merge cu service-role fiindca `profiles` nu are politica de update pe
 * `iban_cont` — dar id-ul vine din sesiune, iar IBAN-ul se ia din baza, dupa ce se
 * verifica proprietatea, niciodata din formular.
 */
export async function faContulPrincipal(idCont: string): Promise<RezultatCont> {
  const supabase = await createClient();
  const supabaseAdmin = createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie să fii autentificat." };

  // IBAN-ul se citeste din baza, cu clientul utilizatorului: asa RLS confirma
  // proprietatea, si nimeni nu poate trimite IBAN-ul altcuiva din browser.
  const { data: cont, error: eroareCont } = await supabase
    .from("conturi_bancare")
    .select("iban, blocat_administrativ, inchis_la")
    .eq("id", idCont)
    .eq("id_user", user.id)
    .maybeSingle();

  if (eroareCont) {
    console.error("ERROR faContulPrincipal (citire):", eroareCont);
    return { eroare: "Nu am putut citi contul. Încearcă din nou." };
  }

  if (!cont || cont.inchis_la) {
    return { eroare: "Contul nu mai există sau a fost închis." };
  }

  // Un cont blocat nu poate fi principal: la inchiderea relatiei, consolidarea
  // se opreste pe CONT_BLOCAT si omul ar ramane blocat intr-un pas pe care nu-l
  // poate rezolva singur.
  if (cont.blocat_administrativ) {
    return { eroare: "Un cont blocat de bancă nu poate deveni cont principal." };
  }

  const { error } = await supabaseAdmin
    .from("profiles")
    .update({ iban_cont: cont.iban })
    .eq("id", user.id);

  if (error) {
    console.error("ERROR faContulPrincipal:", error);
    return { eroare: "Nu am putut schimba contul principal. Încearcă din nou." };
  }

  revalidatePath("/dashboard");
  revalidatePath("/transfer");
  revalidatePath("/setari");

  return {};
}

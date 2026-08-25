"use server";

import { revalidatePath } from "next/cache";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";
import { VALUTE, type Valuta } from "@/lib/valute";

export type RezultatSchimb = { eroare?: string };

export type RezultatSchimbSuma = {
  eroare?: string;
  contNou?: boolean;
  valutaDestinatie?: string;
};

/** Codurile ridicate de public.schimba_valuta_cont/schimba_valuta_suma (0013, 0019_schimb_valutar_suma.sql). */
const MESAJE: Record<string, string> = {
  NEAUTENTIFICAT: "Trebuie să fii autentificat.",
  NEAUTORIZAT: "Nu poți schimba valuta unui cont care nu e al tău.",
  CONT_STRAIN: "Nu poți schimba valuta unui cont care nu e al tău.",
  CONT_INEXISTENT: "Contul nu mai există.",
  ACEEASI_VALUTA: "Contul e deja în această valută.",
  VALUTA_NESUPORTATA: "Se poate schimba doar în RON, EUR, USD, GBP sau CHF.",
  SUMA_INVALIDA: "Suma introdusă nu este validă.",
  SUMA_PREA_MICA: "Suma e prea mică pentru a fi convertită în această valută.",
  FONDURI_INSUFICIENTE: "Nu ai fonduri suficiente pentru această sumă.",
  CONTURI_LIMITA: "Ai atins numărul maxim de conturi.",
  CURS_INDISPONIBIL:
    "Nu am cursul BNR pentru această valută. Încearcă din nou în câteva minute.",
};

/**
 * Schimba intreg soldul unui cont in alta valuta, la cursul BNR.
 *
 * Toata conversia se face in public.schimba_valuta_cont, sub lock, cu cursul
 * citit din public.curs_valutar — clientul nu trimite niciun curs, doar contul
 * si valuta dorita. Aici raman validarile de formular.
 */
export async function schimbaValuta(
  idCont: string,
  valuta: Valuta,
): Promise<RezultatSchimb> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie să fii autentificat." };

  if (!VALUTE.includes(valuta)) {
    return { eroare: "Valuta aleasă nu este acceptată." };
  }

  // Apelul merge cu service_role si p_id_user din sesiune, ca la transfer:
  // functia verifica oricum ca acel cont e al utilizatorului.
  const supabaseAdmin = createAdminClient();

  const { error } = await supabaseAdmin.rpc("schimba_valuta_cont", {
    p_id_cont: idCont,
    p_valuta_noua: valuta,
    p_id_user: user.id,
  });

  if (error) {
    const mesaj = MESAJE[error.message];

    if (!mesaj) console.error("ERROR schimbaValuta:", error);

    return { eroare: mesaj ?? "Nu am putut schimba valuta. Încearcă din nou." };
  }

  revalidatePath("/dashboard");
  revalidatePath("/carduri");
  revalidatePath("/transfer");

  return {};
}

/**
 * Schimba o suma partiala dintr-un cont sursa intr-o valuta noua.
 *
 * Banii ajung intr-un cont separat, in acea valuta — creat automat (fara pas
 * de confirmare) daca utilizatorul nu are inca unul, la fel ca la deschiderea
 * manuala de cont (deschideCont), doar fara nume ales de utilizator. Toata
 * logica (validare, cont nou, conversie, sub lock) sta in
 * public.schimba_valuta_suma (0019_schimb_valutar_suma.sql) — aici raman doar
 * validarile de formular si maparea codurilor de eroare.
 */
export async function schimbaValutaSuma(
  idContSursa: string,
  suma: number,
  valuta: Valuta,
): Promise<RezultatSchimbSuma> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie să fii autentificat." };

  if (!VALUTE.includes(valuta)) {
    return { eroare: "Valuta aleasă nu este acceptată." };
  }

  if (!Number.isFinite(suma) || suma <= 0) {
    return { eroare: "Introdu o sumă mai mare decât 0." };
  }

  const supabaseAdmin = createAdminClient();

  const { data, error } = await supabaseAdmin.rpc("schimba_valuta_suma", {
    p_id_cont_sursa: idContSursa,
    p_suma: suma,
    p_valuta_noua: valuta,
    p_id_user: user.id,
  });

  if (error) {
    const mesaj = MESAJE[error.message];

    if (!mesaj) console.error("ERROR schimbaValutaSuma:", error);

    return { eroare: mesaj ?? "Nu am putut face schimbul. Încearcă din nou." };
  }

  revalidatePath("/dashboard");
  revalidatePath("/carduri");
  revalidatePath("/transfer");

  return { contNou: Boolean(data?.cont_nou), valutaDestinatie: data?.valuta_destinatie };
}

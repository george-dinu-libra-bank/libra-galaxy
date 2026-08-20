"use server";

import { revalidatePath } from "next/cache";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";
import { VALUTE, type Valuta } from "@/lib/valute";

export type RezultatSchimb = { eroare?: string };

/** Codurile ridicate de public.schimba_valuta_cont (0013_schimb_valutar.sql). */
const MESAJE: Record<string, string> = {
  NEAUTENTIFICAT: "Trebuie să fii autentificat.",
  NEAUTORIZAT: "Nu poți schimba valuta unui cont care nu e al tău.",
  CONT_STRAIN: "Nu poți schimba valuta unui cont care nu e al tău.",
  CONT_INEXISTENT: "Contul nu mai există.",
  ACEEASI_VALUTA: "Contul e deja în această valută.",
  VALUTA_NESUPORTATA: "Se poate schimba doar în RON, EUR, USD, GBP sau CHF.",
  SUMA_PREA_MICA: "Soldul e prea mic pentru a fi convertit în această valută.",
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

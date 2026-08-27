"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

/**
 * Cererea clientului de a-si inchide un CONT BANCAR (nu relatia cu banca).
 *
 * Merge direct prin RLS, cu clientul autentificat, nu prin backend — spre
 * deosebire de partea de admin, care are nevoie de service-role ca sa mute bani.
 * Politicile din migratia 0040 fac toata munca de autorizare: „depune" cere
 * `auth.uid() = id_utilizator`, iar „retrage" il lasa doar pe randurile lui inca
 * in asteptare. Acelasi tipar ca `deschideCont` — cererea nu are nevoie de
 * privilegii pe care omul nu le are deja.
 *
 * Ce NU se verifica aici: contul principal, contul blocat, soldul negativ.
 * Acelea sunt garzi in `public.inchide_cont_bancar` si se aplica la decizie. Un
 * client poate depune cererea; banca e cea care spune nu.
 */

export type RezultatInchidere = { eroare?: string };

function reincarca() {
  revalidatePath("/dashboard");
  revalidatePath("/transfer");
  revalidatePath("/carduri");
}

export async function cereInchidereaContului(
  idCont: string,
  idContDestinatie: string | null,
  motivBrut: string,
): Promise<RezultatInchidere> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie să fii autentificat." };

  const motiv = motivBrut.trim().slice(0, 500) || null;

  const { error } = await supabase.from("cereri_inchidere_cont").insert({
    id_utilizator: user.id,
    id_cont: idCont,
    id_cont_destinatie: idContDestinatie,
    motiv,
  });

  if (error) {
    // 23505 = indexul unic partial pe cererile deschise. Nu e o defectiune, e
    // exact ce trebuia sa se intample — dar mesajul brut al bazei n-are ce cauta
    // in fata omului.
    if (error.code === "23505") {
      return { eroare: "Ai deja o cerere de închidere în analiză pentru acest cont." };
    }
    console.error("ERROR cereInchidereaContului:", error);
    return { eroare: "Nu am putut trimite cererea. Încearcă din nou." };
  }

  reincarca();
  return {};
}

export async function retrageInchidereaContului(idCerere: string): Promise<RezultatInchidere> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie să fii autentificat." };

  const { data, error } = await supabase
    .from("cereri_inchidere_cont")
    .update({ status: "retrasa" })
    .eq("id", idCerere)
    .eq("id_utilizator", user.id)
    .eq("status", "in_asteptare")
    .select("id");

  if (error) {
    console.error("ERROR retrageInchidereaContului:", error);
    return { eroare: "Nu am putut retrage cererea. Încearcă din nou." };
  }

  // Zero randuri inseamna ca intre timp a decis banca. Nu e o eroare tehnica, si
  // omul trebuie sa afle ce s-a intamplat, nu sa vada butonul cum nu face nimic.
  if (!data || data.length === 0) {
    return { eroare: "Cererea a fost deja decisă de bancă." };
  }

  reincarca();
  return {};
}

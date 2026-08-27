"use server";

import { revalidatePath } from "next/cache";
import { backendFetch, BackendError } from "@/lib/backend";
import { createClient } from "@/lib/supabase/server";

export type RezultatSesizare = {
  eroare?: string;
  /** Fals cand exista deja o sesizare deschisa — nu s-a creat una noua. */
  creataAcum?: boolean;
};

/**
 * Trimite catre banca sesizarea pregatita de asistent.
 *
 * Se cheama doar din butonul aratat in chat, dupa ce clientul a citit exact
 * textul care pleaca. Asistentul nu scrie nimic singur: tool-ul lui e
 * `PREPARES_MUTATION` si se opreste la compunerea rezumatului.
 */
export async function trimiteSesizare(
  subiect: string,
  rezumat: string,
): Promise<RezultatSesizare> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) return { eroare: "Trebuie să fii autentificat." };

  try {
    const rezultat = await backendFetch<{ id: string; creata_acum: boolean }>(
      "api/v1/suport",
      session.access_token,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subiect, rezumat, context: {} }),
      },
    );

    revalidatePath("/asistent");
    return { creataAcum: rezultat.creata_acum };
  } catch (exc) {
    return {
      eroare:
        exc instanceof BackendError
          ? exc.message
          : "Nu am putut trimite sesizarea. Încearcă din nou.",
    };
  }
}

"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";

export type RezultatRaspuns = { eroare?: string };

/**
 * Raspunde unei sesizari. Clientul primeste raspunsul si ca notificare.
 *
 * Rolul se verifica si aici, nu doar pe ecranul din care se apeleaza: o actiune
 * de server e un endpoint ca oricare altul. Backendul o verifica din nou —
 * aceea e cea care conteaza.
 */
export async function raspundeSesizare(
  idSesizare: string,
  raspuns: string,
  status: "in_lucru" | "rezolvata" = "rezolvata",
): Promise<RezultatRaspuns> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/suport/${encodeURIComponent(idSesizare)}/raspuns`, admin.token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raspuns, status }),
    });

    revalidatePath("/admin/sesizari");
    return {};
  } catch (exc) {
    return {
      eroare:
        exc instanceof BackendError
          ? exc.message
          : "Nu am putut trimite răspunsul. Încearcă din nou.",
    };
  }
}

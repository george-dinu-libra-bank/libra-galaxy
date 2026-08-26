"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";

export type RezultatStergere = { eroare?: string };

/**
 * Deciziile analistului pe cererile de inchidere a contului.
 *
 * Rolul se verifica si aici, nu doar pe ecranul din care se apeleaza: o actiune
 * de server e un endpoint ca oricare altul. Backendul il verifica a doua oara,
 * iar RLS-ul a treia — aceea e cea care conteaza.
 */

export async function decideCerereStergere(
  idCerere: string,
  aproba: boolean,
  motiv?: string,
): Promise<RezultatStergere> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/admin/cereri-stergere/${idCerere}/decizie`, admin.token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aproba, motiv: motiv?.trim() || null }),
    });
  } catch (eroare) {
    return {
      eroare:
        eroare instanceof BackendError
          ? eroare.message
          : "Nu am putut înregistra decizia. Încearcă din nou.",
    };
  }

  revalidatePath("/admin/conturi");
  return {};
}

export async function stergeClientul(idCerere: string): Promise<RezultatStergere> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/admin/cereri-stergere/${idCerere}/sterge`, admin.token, {
      method: "POST",
    });
  } catch (eroare) {
    // Mesajele vin din RPC (0038): CONTURI_CU_SOLD, CONTURI_BLOCATE,
    // CREDITE_IN_DERULARE. Se arata ca atare — spun exact ce mai e de facut.
    return {
      eroare:
        eroare instanceof BackendError
          ? eroare.message
          : "Nu am putut șterge clientul. Încearcă din nou.",
    };
  }

  revalidatePath("/admin/conturi");
  return {};
}

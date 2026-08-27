"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";

/**
 * Deciziile analistului pe cererile de inchidere a unui cont bancar.
 *
 * Rolul se verifica si aici, nu doar pe ecranul din care se apeleaza: o actiune
 * de server e un endpoint ca oricare altul. Backendul il verifica a doua oara,
 * iar RLS-ul a treia — aceea e cea care conteaza.
 */

export type RezultatInchidere = { eroare?: string };

export async function decideInchidereaContului(
  idCerere: string,
  aproba: boolean,
  optiuni: { idContDestinatie?: string | null; motiv?: string } = {},
): Promise<RezultatInchidere> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/admin/cereri-inchidere-cont/${idCerere}/decizie`, admin.token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        aproba,
        // Lipsa inseamna „automat": RPC-ul cade pe propunerea clientului, iar
        // daca nici ea nu exista, pe contul principal.
        id_cont_destinatie: optiuni.idContDestinatie ?? null,
        motiv: optiuni.motiv?.trim() || null,
      }),
    });
  } catch (eroare) {
    // Mesajele vin din RPC (0040): CONT_PRINCIPAL, CONT_BLOCAT, SOLD_NEGATIV,
    // DESTINATIE_INVALIDA. Se arata ca atare — spun exact ce s-a oprit si de ce.
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

export async function redeschideContul(idCont: string): Promise<RezultatInchidere> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/admin/conturi/${idCont}/redeschide`, admin.token, {
      method: "POST",
    });
  } catch (eroare) {
    return {
      eroare:
        eroare instanceof BackendError
          ? eroare.message
          : "Nu am putut redeschide contul. Încearcă din nou.",
    };
  }

  revalidatePath("/admin/conturi");
  return {};
}

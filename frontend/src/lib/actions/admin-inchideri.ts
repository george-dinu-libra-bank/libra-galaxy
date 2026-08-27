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
    // Codurile ridicate de RPC (0040-0042) — CONT_PRINCIPAL, CONT_BLOCAT,
    // SOLD_NEGATIV, DESTINATIE_INVALIDA, CERERE_DECISA — sunt traduse in mesaje
    // de ruta de admin (`MESAJE_INCHIDERE`), asa ca ajung aici gata scrise: spun
    // exact ce s-a oprit si de ce, in loc de „eroare neasteptata" cu 500.
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
    // La fel ca mai sus: CONT_NEINCHIS („contul nu e inchis") vine deja tradus,
    // cu 409, nu ca 500.
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

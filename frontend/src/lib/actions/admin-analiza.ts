"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";
import type { Decizie, RezultatAnaliza } from "@/lib/tipuri-admin";

export type RezultatDecizieCont = { eroare?: string; rezultat?: RezultatAnaliza };

/**
 * Consemneaza hotararea administratorului asupra unui cont semnalat.
 *
 * Verificarea de rol se face si aici, nu doar pe ecranul din care se apeleaza:
 * o actiune de server e un endpoint ca oricare altul, care poate fi chemat
 * direct. Backendul o verifica din nou — aceea e cea care conteaza.
 */
export async function decideCont(
  idUtilizator: string,
  decizie: Decizie,
  observatie: string,
  context: {
    gravitate?: number;
    numarSemnalari?: number;
    zile?: number;
    /** Blocarea se cere anume; nu decurge din verdict. */
    aplicaBlocarea?: boolean;
  } = {},
): Promise<RezultatDecizieCont> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    const rezultat = await backendFetch<RezultatAnaliza>(
      `api/v1/admin/cont/${encodeURIComponent(idUtilizator)}/analiza`,
      admin.token,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decizie,
          observatie: observatie.trim() || null,
          gravitate: context.gravitate ?? null,
          numar_semnalari: context.numarSemnalari ?? null,
          zile: context.zile ?? null,
          aplica_blocarea: context.aplicaBlocarea ?? false,
        }),
      },
    );

    revalidatePath("/admin/tranzactii");
    revalidatePath(`/admin/tranzactii/${idUtilizator}`);
    return { rezultat };
  } catch (exc) {
    return {
      eroare:
        exc instanceof BackendError
          ? exc.message
          : "Nu am putut salva decizia. Încearcă din nou.",
    };
  }
}

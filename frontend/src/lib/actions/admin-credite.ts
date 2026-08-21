"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";

export type RezultatDecizieCredit = { eroare?: string; status?: string };

/**
 * Verificarea de rol se face si aici, nu doar pe ecranul din care se apeleaza:
 * o actiune de server e un endpoint ca oricare altul, care poate fi chemat
 * direct. Backendul o verifica a treia oara — aia e cea care conteaza.
 */
async function cuAdmin<T>(
  apel: (token: string) => Promise<T>,
): Promise<{ date?: T; eroare?: string }> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul sa faci asta." };

  try {
    return { date: await apel(admin.token) };
  } catch (eroare) {
    if (eroare instanceof BackendError) return { eroare: eroare.message };
    return { eroare: "Nu am putut trimite cererea. Încearcă din nou." };
  }
}

/**
 * Aproba sau respinge o cerere din zona gri.
 *
 * Aprobarea NU acorda creditul — genereaza oferta. Clientul o accepta tot el,
 * din aplicatie: semnatura ramane a lui, nu a administratorului.
 */
export async function decideCerereCredit(
  idCerere: string,
  aproba: boolean,
  nota?: string,
): Promise<RezultatDecizieCredit> {
  const rezultat = await cuAdmin((token) =>
    backendFetch<{ status: string }>(
      `api/v1/admin/credite/cereri/${encodeURIComponent(idCerere)}/decizie`,
      token,
      { method: "POST", body: JSON.stringify({ aproba, nota: nota?.trim() || null }) },
    ),
  );

  if (rezultat.eroare) return { eroare: rezultat.eroare };

  revalidatePath("/admin/credite");
  revalidatePath(`/admin/credite/${idCerere}`);
  return { status: rezultat.date?.status };
}

/**
 * Valideaza cifra citita din adeverinta.
 *
 * Analistul completeaza o intrare a motorului de scoring, nu alege un rezultat:
 * dupa confirmare ruleaza acelasi calcul determinist, cu venitul in plus. De
 * aceea scorul se poate schimba imediat, fara ca nimeni sa fi apasat „aproba".
 */
export async function confirmaVenitDinAdeverinta(
  idDocument: string,
  idCerere: string,
  venitConfirmat: string,
): Promise<RezultatDecizieCredit> {
  const rezultat = await cuAdmin((token) =>
    backendFetch<{ cerere: { status: string } }>(
      `api/v1/admin/credite/documente/${encodeURIComponent(idDocument)}/confirma`,
      token,
      { method: "POST", body: JSON.stringify({ venit_confirmat: venitConfirmat }) },
    ),
  );

  if (rezultat.eroare) return { eroare: rezultat.eroare };

  revalidatePath("/admin/credite");
  revalidatePath(`/admin/credite/${idCerere}`);
  return { status: rezultat.date?.cerere.status };
}

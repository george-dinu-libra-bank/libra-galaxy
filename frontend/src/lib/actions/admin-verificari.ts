"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";

export type RezultatDecizie = { eroare?: string; status?: string };

/**
 * Aproba sau respinge un caz de verificare.
 *
 * Verificarea de rol se face si aici, nu doar pe ecranul din care se apeleaza:
 * o actiune de server e un endpoint ca oricare altul, care poate fi chemat
 * direct. Backendul o verifica a treia oara — asta e cea care conteaza.
 */
export async function decideVerificare(
  verificationId: string,
  decizie: "verified" | "rejected",
  note?: string,
): Promise<RezultatDecizie> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul sa faci asta." };

  try {
    const rezultat = await backendFetch<{ status: string }>(
      "api/identity/admin/review",
      admin.token,
      {
        method: "POST",
        body: JSON.stringify({
          verification_id: verificationId,
          decizie,
          note: note?.trim() || null,
        }),
      },
    );

    revalidatePath("/admin");
    revalidatePath(`/admin/verificari/${verificationId}`);
    return { status: rezultat.status };
  } catch (eroare) {
    if (eroare instanceof BackendError) return { eroare: eroare.message };
    return { eroare: "Nu am putut salva decizia. Incearca din nou." };
  }
}

/**
 * Marcheaza manual un cont ca verificat, fara OCR/selfie — pentru conturi
 * ramase pe 'pending' fara sa apuce sa trimita dovezi.
 */
export async function forteazaVerificare(
  userId: string,
  note?: string,
): Promise<RezultatDecizie> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul sa faci asta." };

  try {
    const rezultat = await backendFetch<{ verification_status: string }>(
      "api/identity/admin/forteaza-verificare",
      admin.token,
      {
        method: "POST",
        body: JSON.stringify({ user_id: userId, note: note?.trim() || null }),
      },
    );

    revalidatePath("/admin");
    return { status: rezultat.verification_status };
  } catch (eroare) {
    if (eroare instanceof BackendError) return { eroare: eroare.message };
    return { eroare: "Nu am putut marca contul ca verificat. Incearca din nou." };
  }
}

"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";
import { createAdminClient } from "@/lib/supabase/admin";

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

/**
 * Restabileste manual referinta biometrica a unui cont, cu o poza noua —
 * pentru cazul in care pozele din storage au disparut si login-ul biometric
 * nu mai are cu ce sa compare.
 */
export async function restabilesteBiometrie(
  userId: string,
  poza: File,
): Promise<RezultatDecizie> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul sa faci asta." };

  const supabaseAdmin = await createAdminClient();
  const calePoza = `${userId}/selfie-admin-${Date.now()}.jpg`;

  const { error: eroareIncarcare } = await supabaseAdmin.storage
    .from("selfie-uri")
    .upload(calePoza, poza, { contentType: poza.type || "image/jpeg", upsert: false });

  if (eroareIncarcare) {
    console.error("[admin-verificari/restabilesteBiometrie] cod=upload_storage_esuat", eroareIncarcare.message);
    return { eroare: "Nu am putut incarca poza." };
  }

  try {
    const rezultat = await backendFetch<{ verification_status: string }>(
      "api/identity/admin/restabileste-biometrie",
      admin.token,
      {
        method: "POST",
        body: JSON.stringify({ user_id: userId, poza_path: calePoza }),
      },
    );

    revalidatePath("/admin/conturi");
    return { status: rezultat.verification_status };
  } catch (eroare) {
    if (eroare instanceof BackendError) return { eroare: eroare.message };
    return { eroare: "Nu am putut salva referinta biometrica. Incearca din nou." };
  }
}

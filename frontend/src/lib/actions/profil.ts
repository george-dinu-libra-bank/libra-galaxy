"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "../supabase/admin";

/**
 * Poza de profil. Scrierea in Storage si pe profil se face cu service_role, ca
 * la carduri si transferuri; clientul utilizatorului ramane doar pentru
 * `getUser()`, iar calea fisierului e construita mereu din `user.id`, deci
 * nimeni nu poate atinge folderul altcuiva chiar daca politicile din
 * 0005_avatar_profil.sql lipsesc.
 *
 * Important: toate operatiile pe bucket trebuie sa foloseasca acelasi client.
 * Cu service_role la upload si clientul userului la stergere, curatarea pica
 * tacut si raman fisiere orfane in bucket.
 */

const BUCKET = "avatare";
const MAX_OCTETI = 4 * 1024 * 1024;
const TIPURI: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
};

export type RezultatAvatar = { url?: string | null; eroare?: string };

type SupabaseAdmin = Awaited<ReturnType<typeof createAdminClient>>;

/** Sterge pozele vechi ale utilizatorului, pastrand-o eventual pe cea curenta. */
async function curataFolderul(
  supabaseAdmin: SupabaseAdmin,
  idUser: string,
  calePastrata?: string,
) {
  const { data, error } = await supabaseAdmin.storage.from(BUCKET).list(idUser);

  if (error || !data?.length) return;

  const vechi = data
    .map((fisier) => `${idUser}/${fisier.name}`)
    .filter((cale) => cale !== calePastrata);

  if (vechi.length) await supabaseAdmin.storage.from(BUCKET).remove(vechi);
}

/**
 * Urca poza aleasa (din galerie sau facuta cu camera) si o leaga de profil.
 * Intai fisierul, apoi profilul: daca update-ul pica, stergem fisierul ca sa nu
 * ramana orfan in bucket.
 */
export async function salveazaAvatar(formData: FormData): Promise<RezultatAvatar> {
  const supabase = await createClient();
  const supabaseAdmin = await createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const poza = formData.get("poza");

  if (!(poza instanceof File) || poza.size === 0) {
    return { eroare: "Alege o poza sau fă una cu camera." };
  }

  const extensie = TIPURI[poza.type];

  if (!extensie) return { eroare: "Poza trebuie să fie JPG, PNG sau WebP." };
  if (poza.size > MAX_OCTETI) return { eroare: "Poza este prea mare (maxim 4 MB)." };

  const cale = `${user.id}/avatar-${Date.now()}.${extensie}`;

  const { error: eroareIncarcare } = await supabaseAdmin.storage
    .from(BUCKET)
    .upload(cale, poza, { contentType: poza.type, upsert: false });

  if (eroareIncarcare) {
    console.error("ERROR salveazaAvatar (storage):", eroareIncarcare);
    return { eroare: "Nu am putut încărca poza. Încearcă din nou." };
  }

  const {
    data: { publicUrl },
  } = supabaseAdmin.storage.from(BUCKET).getPublicUrl(cale);

  const { error } = await supabaseAdmin
    .from("profiles")
    .update({ avatar_url: publicUrl })
    .eq("id", user.id);

  if (error) {
    console.error("ERROR salveazaAvatar (profil):", error);
    await supabaseAdmin.storage.from(BUCKET).remove([cale]);
    return { eroare: "Nu am putut salva poza. Încearcă din nou." };
  }

  await curataFolderul(supabaseAdmin, user.id, cale);

  revalidatePath("/dashboard");
  revalidatePath("/setari");

  return { url: publicUrl };
}

/** Revine la iconita implicita: sterge legatura din profil si fisierele. */
export async function stergeAvatar(): Promise<RezultatAvatar> {
  const supabase = await createClient();
  const supabaseAdmin = await createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const { error } = await supabaseAdmin
    .from("profiles")
    .update({ avatar_url: null })
    .eq("id", user.id);

  if (error) {
    console.error("ERROR stergeAvatar:", error);
    return { eroare: "Nu am putut șterge poza. Încearcă din nou." };
  }

  await curataFolderul(supabaseAdmin, user.id);

  revalidatePath("/dashboard");
  revalidatePath("/setari");

  return { url: null };
}

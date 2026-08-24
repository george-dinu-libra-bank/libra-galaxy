"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

/**
 * Marcheaza o notificare drept citita.
 *
 * Doar `citita_la` se scrie. Textul e aparat si de un trigger in baza de date
 * (`notificari_pastreaza_textul`), ca cineva sa nu poata rescrie motivul
 * pentru care i s-a blocat contul.
 */
export async function marcheazaCitita(id: string): Promise<{ eroare?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { eroare: "Trebuie să fii autentificat." };

  const { error } = await supabase
    .from("notificari")
    .update({ citita_la: new Date().toISOString() })
    .eq("id", id)
    .eq("id_utilizator", user.id);

  if (error) return { eroare: "Nu am putut marca notificarea." };

  revalidatePath("/dashboard");
  return {};
}

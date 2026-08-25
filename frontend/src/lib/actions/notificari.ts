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

/**
 * Marcheaza tot ce e necitit.
 *
 * Filtrul pe utilizator nu e redundant fata de RLS: politica de select pe
 * `notificari` e `auth.uid() = id_utilizator OR este_administrator()`, deci un
 * administrator vede si notificarile altora — dar politica de update permite
 * doar randurile proprii. Fara filtru, actualizarea atingea 0 randuri pentru
 * cele straine si parea ca butonul nu merge.
 */
export async function marcheazaToateCitite(): Promise<{ eroare?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { eroare: "Trebuie să fii autentificat." };

  const { error } = await supabase
    .from("notificari")
    .update({ citita_la: new Date().toISOString() })
    .eq("id_utilizator", user.id)
    .is("citita_la", null);

  if (error) return { eroare: "Nu am putut marca notificările." };

  revalidatePath("/dashboard");
  return {};
}

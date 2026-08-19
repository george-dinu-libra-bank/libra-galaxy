"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import type { StilCard } from "@/lib/data/carduri";

export type RezultatCard = { eroare?: string };

/**
 * Creeaza un card nou pentru utilizatorul curent. Numarul, CCV-ul si data
 * expirarii se genereaza in baza de date (trigger pe INSERT) — aici trimitem
 * doar tematica aleasa.
 */
export async function adaugaCard(cardStyle: StilCard): Promise<RezultatCard> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const { error } = await supabase
    .from("carduri")
    .insert({ id_user: user.id, card_style: cardStyle });

  if (error) return { eroare: "Nu am putut crea cardul. Incearca din nou." };

  revalidatePath("/dashboard");
  revalidatePath("/carduri");

  return {};
}

/** Blocheaza/deblocheaza un card propriu. */
export async function comutaBlocareCard(id: string, blocat: boolean): Promise<RezultatCard> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const { error } = await supabase
    .from("carduri")
    .update({ is_blocked: blocat })
    .eq("id", id)
    .eq("id_user", user.id);

  if (error) return { eroare: "Nu am putut actualiza cardul." };

  revalidatePath("/dashboard");
  revalidatePath("/carduri");

  return {};
}

"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import type { Beneficiar } from "@/lib/data/beneficiari";

export type RezultatBeneficiar = { beneficiar?: Beneficiar; eroare?: string };
export type RezultatMesaj = { eroare?: string };

/**
 * Mesajele pentru utilizator, dupa codul ridicat de beneficiari_before_insert
 * (0045_beneficiari.sql): codul ajunge in `message`, textul lung in `details`.
 */
const MESAJE_BENEFICIARI: Record<string, string> = {
  NUME_INVALID: "Numele trebuie sa aiba intre 2 si 60 de caractere.",
  IBAN_INVALID: "IBAN invalid.",
  PROPRIUL_CONT: "Nu te poți adăuga singur ca beneficiar.",
};

/** Adauga un beneficiar nou. Legatura cu un cont Galaxy Bank (daca exista) se face automat, dupa IBAN. */
export async function adaugaBeneficiar(numeBrut: string, ibanBrut: string): Promise<RezultatBeneficiar> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const nume = numeBrut.trim();
  const iban = ibanBrut.replace(/\s+/g, "").toUpperCase();

  const { data, error } = await supabase
    .from("beneficiari")
    .insert({ id_user: user.id, nume, iban })
    .select("id, nume, iban, banca, favorit, id_user_legat")
    .single();

  if (error) {
    if (error.code === "23505") return { eroare: "Ai deja acest beneficiar salvat." };
    if (!MESAJE_BENEFICIARI[error.message]) console.error("ERROR adaugaBeneficiar:", error);
    return { eroare: MESAJE_BENEFICIARI[error.message] ?? "Nu am putut adăuga beneficiarul. Încearcă din nou." };
  }

  revalidatePath("/beneficiari");

  return {
    beneficiar: {
      id: data.id as string,
      nume: data.nume as string,
      iban: data.iban as string,
      banca: data.banca as string,
      favorit: data.favorit as boolean,
      idUserLegat: (data.id_user_legat as string | null) ?? null,
    },
  };
}

/** Sterge un beneficiar din lista proprie. */
export async function stergeBeneficiar(id: string): Promise<RezultatMesaj> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const { error } = await supabase.from("beneficiari").delete().eq("id", id).eq("id_user", user.id);

  if (error) {
    console.error("ERROR stergeBeneficiar:", error);
    return { eroare: "Nu am putut șterge beneficiarul. Încearcă din nou." };
  }

  revalidatePath("/beneficiari");

  return {};
}

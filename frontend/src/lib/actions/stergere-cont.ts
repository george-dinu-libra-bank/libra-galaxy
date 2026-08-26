"use server";

import { revalidatePath } from "next/cache";
import { apelBackend } from "@/lib/data/backend";

/**
 * Cererea de inchidere a contului.
 *
 * Merge prin FastAPI, nu direct in Supabase: regulile care o blocheaza — credit
 * in derulare, bani ramasi in cont — se verifica in serviciu, unde pot fi
 * testate, nu intr-o politica RLS care ar raspunde doar cu „nu ai voie".
 *
 * Nu sterge nimic. Depune o cerere pe care o decide un om; vezi migratia
 * 0036_cereri_stergere_cont.sql pentru de ce.
 */

const INDISPONIBIL = "Serviciul nu este disponibil momentan. Încearcă din nou.";

export type StareStergere = {
  cerere: { id: string; status: string; creat_la: string } | null;
  poate_cere: boolean;
  motive_blocare: string[];
};

export async function obtineStareStergere(): Promise<{ stare?: StareStergere; eroare?: string }> {
  const { date, eroare } = await apelBackend<StareStergere>("/api/v1/me/stergere", {}, INDISPONIBIL);
  if (eroare || !date) return { eroare: eroare ?? INDISPONIBIL };
  return { stare: date };
}

export async function cereStergereaContului(motiv: string): Promise<{ eroare?: string }> {
  const { eroare } = await apelBackend<unknown>(
    "/api/v1/me/stergere",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Sirul gol devine null: „fara motiv" si „motiv gol" sunt acelasi lucru,
      // iar baza pastreaza null, nu "".
      body: JSON.stringify({ motiv: motiv.trim() || null }),
    },
    INDISPONIBIL,
  );

  if (eroare) return { eroare };

  revalidatePath("/dashboard");
  revalidatePath("/setari");
  return {};
}

export async function retrageCerereaDeStergere(id: string): Promise<{ eroare?: string }> {
  const { eroare } = await apelBackend<unknown>(
    `/api/v1/me/stergere/${id}`,
    { method: "DELETE" },
    INDISPONIBIL,
  );

  if (eroare) return { eroare };

  revalidatePath("/dashboard");
  revalidatePath("/setari");
  return {};
}

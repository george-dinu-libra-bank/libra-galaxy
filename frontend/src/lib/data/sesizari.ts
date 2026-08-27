import "server-only";

import { backendFetch } from "@/lib/backend";
import { createClient } from "@/lib/supabase/server";

export type Sesizare = {
  id: string;
  subiect: string;
  rezumat: string;
  status: "deschisa" | "in_lucru" | "rezolvata";
  raspuns: string | null;
  creat_la: string;
};

/**
 * Sesizarile proprii, cu raspunsurile primite.
 *
 * Nu arunca: daca tabela lipseste sau backendul cade, ecranul trebuie sa se
 * vada oricum — omul care vrea sa scrie o sesizare noua nu trebuie oprit de
 * faptul ca nu i se pot arata cele vechi.
 */
export async function obtineSesizarileMele(): Promise<Sesizare[]> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) return [];

  try {
    return await backendFetch<Sesizare[]>("api/v1/suport/ale-mele", session.access_token);
  } catch {
    return [];
  }
}

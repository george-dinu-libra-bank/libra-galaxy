import { laPlataInAsteptare, type PlataInAsteptare, type RandPlata } from "@/lib/plati";
import { createClient } from "@/lib/supabase/server";

export type { PlataInAsteptare };

/**
 * Platile proprii care inca asteapta un raspuns, cea mai veche prima.
 *
 * Realtime aduce platile deschise cat timp ecranul e deschis; asta le aduce pe
 * cele nascute inainte, ca un refresh sa nu piarda un drawer de confirmare.
 * Cele expirate raman afara: nu mai pot fi aprobate oricum.
 */
export async function obtinePlatiInAsteptare(): Promise<PlataInAsteptare[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("payments")
    .select("id, id_user, suma, valuta, comerciant, descriere, card_ultimele4, status, expira_la")
    .eq("id_user", user.id)
    .eq("status", "PENDING_APPROVAL")
    .gt("expira_la", new Date().toISOString())
    .order("creat_la", { ascending: true });

  if (error) {
    // Tabela poate lipsi pe o baza pe care nu s-a rulat inca 0014_payments.sql:
    // restul aplicatiei nu are motiv sa pice pentru atat.
    console.error("ERROR obtinePlatiInAsteptare:", error);
    return [];
  }

  return (data ?? []).map((rand) => laPlataInAsteptare(rand as RandPlata));
}

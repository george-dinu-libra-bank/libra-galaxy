import { backendFetch } from "@/lib/backend";
import type { CerereStergere } from "@/lib/tipuri-admin";

/**
 * Aducerea cererilor de inchidere a relatiei cu banca.
 *
 * Doar atat. Tipurile si regulile („se poate sterge?", „de ce nu?") stau in
 * `@/lib/tipuri-admin`, fiindca de ele are nevoie si componenta de client — iar
 * fisierul asta importa `@/lib/backend`, care e `server-only`.
 */
export async function obtineCereriStergere(token: string): Promise<CerereStergere[]> {
  return backendFetch<CerereStergere[]>("api/v1/admin/cereri-stergere", token);
}

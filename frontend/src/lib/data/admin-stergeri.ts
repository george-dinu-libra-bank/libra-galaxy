import { backendFetch } from "@/lib/backend";
import type { CerereStergere } from "@/lib/cereri-stergere";

export type { ContClient, CerereStergere } from "@/lib/cereri-stergere";

/**
 * Cererile de inchidere a contului, pentru analist.
 *
 * Soldurile si creditele vin odata cu lista, nu la deschiderea fiecarui rand:
 * fara ele, analistul ar apasa „Sterge" si abia RPC-ul i-ar spune de ce nu se
 * poate (0038_sterge_client.sql).
 *
 * Regulile pure (`sePoateSterge`, `motiveleBlocarii`) si tipurile stau in
 * `lib/cereri-stergere.ts`, nu aici — acest fisier importa `lib/backend.ts`
 * (server-only), iar `components/admin/cereri-stergere.tsx` (client) are
 * nevoie de reguli fara sa traga acel import (vezi antetul de acolo).
 */
export async function obtineCereriStergere(token: string): Promise<CerereStergere[]> {
  return backendFetch<CerereStergere[]>("api/v1/admin/cereri-stergere", token);
}

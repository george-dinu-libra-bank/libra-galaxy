import { backendFetch } from "@/lib/backend";
import type { CerereInchidere } from "@/lib/tipuri-admin";

/**
 * Aducerea cererilor de inchidere a unui cont bancar.
 *
 * Ca si la `admin-stergeri.ts`: doar reteaua. Tipurile si regulile stau in
 * `@/lib/tipuri-admin`, ca sa poata fi importate si dintr-o componenta de client
 * fara sa traga dupa ele `server-only`.
 */
export async function obtineCereriInchidere(token: string): Promise<CerereInchidere[]> {
  return backendFetch<CerereInchidere[]>("api/v1/admin/cereri-inchidere-cont", token);
}

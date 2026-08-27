import { backendFetch } from "@/lib/backend";
import type { Poprire } from "@/lib/tipuri-admin";

/**
 * Popririle, pentru panoul analistului.
 *
 * Ca la `admin-inchideri.ts`: doar reteaua. Tipurile si regulile stau in
 * `@/lib/tipuri-admin`, ca sa poata fi importate si dintr-o componenta de client
 * fara sa traga dupa ele `server-only`.
 */
export async function obtinePopriri(token: string): Promise<Poprire[]> {
  return backendFetch<Poprire[]>("api/v1/admin/popriri", token);
}

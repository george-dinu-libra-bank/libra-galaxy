import { backendFetch } from "@/lib/backend";

/**
 * Un caz de verificare a identitatii, asa cum il vede administratorul.
 *
 * `distantaFete` e o DISTANTA, nu o similaritate: mai mic inseamna mai
 * asemanator, iar potrivirea trece cand distanta <= prag. Backendul o numeste
 * deja asa; aici pastram numele, ca sa nu se piarda pe drum sensul si sa
 * ajunga cineva sa respinga un cont bun crezand ca un numar mic e slab.
 */
export type CazVerificare = {
  id: string;
  id_user: string;
  nume: string;
  email: string;
  cnp_declarat: string | null;
  cnp_extras: string | null;
  cnp_se_potriveste: boolean | null;
  distanta_fete: number | null;
  prag: number | null;
  sub_prag: boolean | null;
  status: string;
  creat_la: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  notes: string | null;
};

export type CazVerificareDetaliu = CazVerificare & {
  url_buletin: string | null;
  url_selfie: string | null;
  secunde_valabilitate: number;
};

export async function obtineCazuriDeRevizuit(token: string): Promise<CazVerificare[]> {
  return backendFetch<CazVerificare[]>("api/identity/admin/pending", token);
}

export async function obtineCaz(token: string, id: string): Promise<CazVerificareDetaliu> {
  return backendFetch<CazVerificareDetaliu>(
    `api/identity/admin/case/${encodeURIComponent(id)}`,
    token,
  );
}

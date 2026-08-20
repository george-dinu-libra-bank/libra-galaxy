import { backendFetch } from "@/lib/backend";
import type { CazVerificare, CazVerificareDetaliu } from "@/lib/tipuri-admin";

export async function obtineCazuriDeRevizuit(token: string): Promise<CazVerificare[]> {
  return backendFetch<CazVerificare[]>("api/identity/admin/pending", token);
}

export async function obtineCaz(token: string, id: string): Promise<CazVerificareDetaliu> {
  return backendFetch<CazVerificareDetaliu>(
    `api/identity/admin/case/${encodeURIComponent(id)}`,
    token,
  );
}

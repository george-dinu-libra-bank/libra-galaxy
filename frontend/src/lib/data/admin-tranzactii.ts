import { backendFetch } from "@/lib/backend";
import type { ContSemnalat, Raport } from "@/lib/tipuri-admin";

export async function obtineConturiSemnalate(
  token: string,
  zile: number,
): Promise<ContSemnalat[]> {
  return backendFetch<ContSemnalat[]>(
    `api/v1/admin/conturi-semnalate?zile=${zile}`,
    token,
  );
}

export async function obtineRaport(
  token: string,
  idUtilizator: string,
  zile: number,
  cuSinteza: boolean,
): Promise<Raport> {
  return backendFetch<Raport>(
    `api/v1/admin/raport/${encodeURIComponent(idUtilizator)}` +
      `?zile=${zile}&sinteza=${cuSinteza}`,
    token,
  );
}

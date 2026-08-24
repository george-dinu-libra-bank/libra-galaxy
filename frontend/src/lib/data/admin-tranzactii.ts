import { backendFetch } from "@/lib/backend";
import type {
  ContSemnalat,
  StareCarduri,
  StareCont,
  Raport,
  StareDetectie,
} from "@/lib/tipuri-admin";

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

export async function obtineStareDetectie(token: string): Promise<StareDetectie> {
  return backendFetch<StareDetectie>("api/v1/admin/stare-detectie", token);
}

export async function obtineStareCont(
  token: string,
  idUtilizator: string,
): Promise<StareCont> {
  return backendFetch<StareCont>(
    `api/v1/admin/cont/${encodeURIComponent(idUtilizator)}/istoric`,
    token,
  );
}

export async function obtineStareCarduriToti(token: string): Promise<StareCarduri[]> {
  return backendFetch<StareCarduri[]>("api/v1/admin/stare-carduri", token);
}

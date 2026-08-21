import { backendFetch } from "@/lib/backend";
import type {
  CerereCredit,
  CreditAcordat,
  DosarCredit,
  StatusCerere,
} from "@/lib/tipuri-admin";

/**
 * Cererile care asteapta decizia unui om.
 *
 * Citirea asta declanseaza in backend si curatarea documentelor expirate — nu
 * exista cron in proiect, deci retentia porneste din ceva ce se intampla oricum
 * (vezi `CreditService._curata_documente_expirate`).
 */
export async function obtineCoadaCredite(token: string): Promise<CerereCredit[]> {
  return backendFetch<CerereCredit[]>("api/v1/admin/credite/analiza-manuala", token);
}

/** Toate cererile, optional filtrate — ca sa poata fi auditate si cele automate. */
export async function obtineCereriCredit(
  token: string,
  status?: StatusCerere,
): Promise<CerereCredit[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return backendFetch<CerereCredit[]>(`api/v1/admin/credite/cereri${query}`, token);
}

/** Cererea, verificarile de venit si documentele, intr-un singur apel. */
export async function obtineDosarCredit(token: string, id: string): Promise<DosarCredit> {
  return backendFetch<DosarCredit>(
    `api/v1/admin/credite/cereri/${encodeURIComponent(id)}`,
    token,
  );
}

export async function obtineCrediteAcordate(token: string): Promise<CreditAcordat[]> {
  return backendFetch<CreditAcordat[]>("api/v1/admin/credite/acordate", token);
}

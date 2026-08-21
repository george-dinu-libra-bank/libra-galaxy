import "server-only";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

export class BackendError extends Error {
  constructor(
    public readonly status: number,
    mesaj: string,
  ) {
    super(mesaj);
    this.name = "BackendError";
  }
}

/**
 * Cheama FastAPI direct, din componente si actiuni de server.
 *
 * `lib/api.ts` face acelasi lucru din browser, prin proxy-ul /api/backend;
 * aici suntem deja pe server, deci mergem direct la sursa. Tokenul se trimite
 * explicit — backendul isi verifica singur drepturile, nu se bazeaza pe faptul
 * ca cererea a trecut printr-un ecran care ar fi trebuit sa fie protejat.
 */
export async function backendFetch<T>(
  cale: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const raspuns = await fetch(new URL(cale, `${BACKEND_URL}/`), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!raspuns.ok) {
    const corp = (await raspuns.json().catch(() => null)) as
      | { detail?: string | { mesaj?: string } }
      | null;
    const detaliu = corp?.detail;
    const mesaj =
      typeof detaliu === "string"
        ? detaliu
        : detaliu?.mesaj ?? `${raspuns.status} ${raspuns.statusText}`;
    throw new BackendError(raspuns.status, mesaj);
  }

  if (raspuns.status === 204) return undefined as T;
  return (await raspuns.json()) as T;
}

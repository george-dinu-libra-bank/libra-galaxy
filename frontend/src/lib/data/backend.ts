import { BACKEND_INTERNAL_URL as BACKEND_URL } from "@/lib/env";
import { createClient } from "@/lib/supabase/server";

/**
 * Apelul catre FastAPI, cu tokenul Supabase al utilizatorului curent.
 *
 * Traia in `lib/data/asistent.ts`, unde a fost scris prima oara. A fost mutat
 * aici cand a aparut al doilea consumator (creditarea): doua copii ale aceleiasi
 * functii ar fi divergent la primul bug reparat intr-una din ele (REGULI.md #2).
 * `asistent.ts` il reexporta, deci importurile existente merg neschimbate.
 *
 * Backend-ul nu e niciodata expus catre browser (ARCHITECTURE.md 4.2): functia
 * ruleaza doar server-side, iar clientul vorbeste cu el prin route handler-ul
 * /api/backend/* sau prin server actions.
 */

type PlicSucces<T> = { success: true; body: T };
type PlicEroare = { success: false; error: { code: string; message: string } };

export type RezultatBackend<T> = { date?: T; eroare?: string };

export async function apelBackend<T>(
  cale: string,
  optiuni: RequestInit = {},
  mesajIndisponibil = "Serviciul nu este disponibil momentan. Încearcă din nou.",
): Promise<RezultatBackend<T>> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) return { eroare: "Trebuie sa fii autentificat." };

  let raspuns: Response;
  try {
    raspuns = await fetch(`${BACKEND_URL}${cale}`, {
      ...optiuni,
      headers: {
        ...(optiuni.headers ?? {}),
        Authorization: `Bearer ${session.access_token}`,
        "Accept-Language": "ro",
      },
      cache: "no-store",
    });
  } catch {
    return { eroare: mesajIndisponibil };
  }

  const corp = (await raspuns.json().catch(() => null)) as
    | PlicSucces<T>
    | PlicEroare
    | T
    | null;

  if (corp === null) {
    return { eroare: "A aparut o eroare neasteptata." };
  }

  // Rutele de asistent raspund in plicul standard; cele de sub /api/v1 (alerte,
  // credite) raspund direct cu corpul, iar plicul apare numai la eroare — vezi
  // main.py, unde error_response e legat de handler-ul global, nu de rute.
  if (typeof corp === "object" && "success" in corp) {
    const plic = corp as PlicSucces<T> | PlicEroare;
    return plic.success
      ? { date: plic.body }
      : { eroare: plic.error?.message ?? "A aparut o eroare neasteptata." };
  }

  if (!raspuns.ok) {
    return { eroare: "A aparut o eroare neasteptata." };
  }

  return { date: corp as T };
}

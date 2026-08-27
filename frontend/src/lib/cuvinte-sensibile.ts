import { gasesteCuvinteSensibile } from "@/lib/scanare-cuvinte";
import { createAdminClient } from "@/lib/supabase/admin";


const DURATA_CACHE_MS = 60_000;


let cache: { cuvinte: string[]; expiraLa: number } | null = null;

/** Se apeleaza dupa fiecare salvare din administrare. */
export function invalideazaCuvinteSensibile() {
  cache = null;
}


export async function obtineCuvinteSensibile(): Promise<string[]> {
  if (cache && cache.expiraLa > Date.now()) return cache.cuvinte;

  try {
    const supabaseAdmin = createAdminClient();

    const { data, error } = await supabaseAdmin
      .from("sensitive_words")
      .select("cuvinte")
      .order("actualizat_la", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error) throw error;

    const cuvinte = ((data?.cuvinte as string[] | null) ?? []).filter(
      (cuvant) => cuvant.trim().length > 0,
    );

    cache = { cuvinte, expiraLa: Date.now() + DURATA_CACHE_MS };
    return cuvinte;
  } catch (exc) {
    console.error("ERROR obtineCuvinteSensibile:", exc);
    return [];
  }
}

/**
 * Scaneaza datele unui transfer si intoarce cuvintele gasite.
 *
 * Se uita la tot ce scrie omul de mana — azi, descrierea. Numele
 * beneficiarului nu intra: e ales dintr-o lista de conturi reale, nu scris.
 */
export async function scaneazaTransfer(descriere: string | null): Promise<string[]> {
  if (!descriere?.trim()) return [];

  const cuvinte = await obtineCuvinteSensibile();
  if (cuvinte.length === 0) return [];

  return gasesteCuvinteSensibile(descriere, cuvinte);
}

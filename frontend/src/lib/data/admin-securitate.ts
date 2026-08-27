import { createAdminClient } from "@/lib/supabase/admin";

/**
 * Datele celor doua ecrane de securitate din administrare: lista de cuvinte
 * sensibile si coada transferurilor oprite de ea.
 *
 * Totul se citeste cu service_role. Politicile de pe `sensitive_words` dau
 * accesul administratorilor, dar tranzactiile semnalate ating conturi si
 * profiluri straine, pe care RLS-ul nu le-ar da nici unui administrator prin
 * sesiunea lui. Garda ramane `cereAdmin()`, in pagina.
 */

export type ListaCuvinte = {
  cuvinte: string[];
  actualizatLa: string | null;
};

export async function obtineCuvinteSalvate(): Promise<ListaCuvinte> {
  const supabaseAdmin = createAdminClient();

  const { data, error } = await supabaseAdmin
    .from("sensitive_words")
    .select("cuvinte, actualizat_la")
    .order("actualizat_la", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) throw error;

  return {
    cuvinte: ((data?.cuvinte as string[] | null) ?? []).filter((c) => c.trim().length > 0),
    actualizatLa: (data?.actualizat_la as string | null) ?? null,
  };
}

export type PersoanaSemnalare = { id: string; nume: string; email: string };

export type TranzactieSemnalata = {
  id: string;
  suma: number;
  valuta: string;
  descriere: string | null;
  creatLa: string;
  /** Cuvintele gasite, asa cum sunt scrise in lista administratorului. */
  motiv: string | null;
  expeditor: PersoanaSemnalare | null;
  beneficiar: PersoanaSemnalare | null;
  ibanBeneficiar: string | null;
  /** Setat cand banii au plecat din punga comuna a unui grup. */
  grup: { id: number; nume: string } | null;
};

/** Cand o relatie e ceruta prin `!fkey`, supabase-js o poate da si ca lista. */
function unul<T>(relatie: T | T[] | null): T | null {
  return Array.isArray(relatie) ? (relatie[0] ?? null) : relatie;
}

/**
 * Transferurile care asteapta o decizie, cele mai vechi primele: cine asteapta
 * de mai mult timp cu banii blocati e cel care trebuie rezolvat intai.
 */
export async function obtineTranzactiiSemnalate(): Promise<TranzactieSemnalata[]> {
  const supabaseAdmin = createAdminClient();

  const { data, error } = await supabaseAdmin
    .from("tranzactii")
    .select(
      "id, suma, valuta, descriere, creat_la, motiv_semnalare, " +
        "expeditor:profiles!tranzactii_id_user_send_fkey (id, nume, email), " +
        "beneficiar:profiles!tranzactii_id_user_recieve_fkey (id, nume, email), " +
        "cont_dest:conturi_bancare!tranzactii_id_cont_recieve_fkey (iban), " +
        "grup:groups!tranzactii_id_group_send_fkey (id, nume)",
    )
    .eq("status", "flagged")
    .order("creat_la", { ascending: true });

  if (error) throw error;

  return (data ?? []).map((rand) => {
    const t = rand as unknown as Record<string, unknown>;
    const contDest = unul(t.cont_dest as { iban: string } | { iban: string }[] | null);
    const grup = unul(t.grup as { id: number; nume: string } | { id: number; nume: string }[] | null);

    return {
      id: t.id as string,
      suma: Number(t.suma),
      valuta: t.valuta as string,
      descriere: (t.descriere as string | null) ?? null,
      creatLa: t.creat_la as string,
      motiv: (t.motiv_semnalare as string | null) ?? null,
      expeditor: unul(t.expeditor as PersoanaSemnalare | PersoanaSemnalare[] | null),
      beneficiar: unul(t.beneficiar as PersoanaSemnalare | PersoanaSemnalare[] | null),
      ibanBeneficiar: contDest?.iban ?? null,
      grup: grup ? { id: grup.id, nume: grup.nume } : null,
    };
  });
}

import { apelBackend } from "@/lib/data/backend";

/**
 * Citiri de analiza financiara (cheltuieli pe categorie, cashflow) — trec prin
 * FastAPI, nu direct prin Supabase: categoria e calculata determinist in
 * Python (backend/app/tools/categorii_tranzactii.py) si nu trebuie
 * reimplementata in TypeScript (CLAUDE.md #7).
 */

const INDISPONIBIL = "Analiza financiară nu este disponibilă momentan.";

export type CategorieCheltuiala = {
  categorie: string;
  // O suma pe (categorie, valuta), niciodata convertita de backend — vezi
  // schemas/analiza.py::CategorieCheltuiala. Insumarea intre valute diferite
  // se face client-side, cu cursurile deja aduse (lib/categorii.ts::totalizeazaPeCategorie).
  valuta: string;
  total: number;
};

export type CheltuieliPeCategorie = {
  luna: string; // AAAA-LL
  categorii: CategorieCheltuiala[];
};

export type LunaCashflow = {
  luna: string; // AAAA-LL
  incasari: number;
  cheltuieli: number;
  net: number;
};

export type Cashflow = {
  valuta: string;
  luni: LunaCashflow[];
  mediaLunaraCheltuieli: number;
};

export type TranzactieCategorizata = {
  data: string;
  suma: number;
  valuta: string;
  descriere: string | null;
  directie: "intrare" | "iesire";
  categorie: string;
};

export async function obtineCheltuieliPeCategorie(): Promise<CheltuieliPeCategorie> {
  const { date } = await apelBackend<{
    luna: string;
    categorii: { categorie: string; valuta: string; total: number }[];
  }>("/api/v1/analiza/cheltuieli-pe-categorie", {}, INDISPONIBIL);

  return date ?? { luna: "", categorii: [] };
}

export async function obtineCashflow(luni: number = 1): Promise<Cashflow | null> {
  const { date } = await apelBackend<{
    valuta: string;
    luni: { luna: string; incasari: number; cheltuieli: number; net: number }[];
    media_lunara_cheltuieli: number;
  }>(`/api/v1/analiza/cashflow?luni=${luni}`, {}, INDISPONIBIL);

  if (!date) return null;
  return { valuta: date.valuta, luni: date.luni, mediaLunaraCheltuieli: date.media_lunara_cheltuieli };
}

export async function obtineTranzactiiCategorizate(
  zile: number = 31,
  limita: number = 200,
): Promise<TranzactieCategorizata[]> {
  const { date } = await apelBackend<TranzactieCategorizata[]>(
    `/api/v1/analiza/tranzactii-categorizate?zile=${zile}&limita=${limita}`,
    {},
    INDISPONIBIL,
  );

  return date ?? [];
}

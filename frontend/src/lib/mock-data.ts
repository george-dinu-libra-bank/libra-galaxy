/**
 * Date simulate — nu exista inca tabele Supabase pentru conturi (IBAN) si
 * beneficiari externi (doar `profiles`, `carduri`, `tranzactii`; vezi
 * lib/data/carduri.ts si lib/data/tranzactii.ts pentru datele reale).
 * Functiile de mai jos sunt async si intorc forme apropiate de ce va veni
 * de la API, ca inlocuirea ulterioara sa fie directa.
 */

export type TipCont = "curent" | "economii";

export type Cont = {
  id: string;
  tip: TipCont;
  nume: string;
  iban: string;
  sold: number;
  valuta: string;
};

export type Beneficiar = {
  id: string;
  nume: string;
  iban: string;
  banca: string;
  favorit: boolean;
};

const CONTURI: Cont[] = [
  {
    id: "cont-curent",
    tip: "curent",
    nume: "Cont curent",
    iban: "RO49LIBR1B310075938400",
    sold: 4287.52,
    valuta: "RON",
  },
  {
    id: "cont-economii",
    tip: "economii",
    nume: "Economii",
    iban: "RO12LIBR9F204488310017",
    sold: 12500,
    valuta: "RON",
  },
];

const BENEFICIARI: Beneficiar[] = [
  {
    id: "b1",
    nume: "Andrei Popescu",
    iban: "RO91BTRL0000000012345678",
    banca: "Banca Transilvania",
    favorit: true,
  },
  {
    id: "b2",
    nume: "Maria Ionescu",
    iban: "RO49BRDE310SV00012345601",
    banca: "BRD",
    favorit: true,
  },
  {
    id: "b3",
    nume: "Enel Energie",
    iban: "RO22RNCB0082000123456789",
    banca: "BCR",
    favorit: false,
  },
  {
    id: "b4",
    nume: "Cristina Dumitrescu",
    iban: "RO35INGB0000999912345678",
    banca: "ING Bank",
    favorit: false,
  },
];

/** Folosit pe dashboard si in Setari cat timp nu exista credentiale Supabase reale. */
export const PROFIL_DEMO = {
  nume: "Ana Popescu",
  cnp: "2960101123456",
  telefon: "+40712345678",
  email: "ana.popescu@exemplu.ro",
  iban_cont: "RO49LIBR1B310075938400",
  creat_la: "2025-01-15T09:00:00.000Z",
};

export async function obtineConturi(): Promise<Cont[]> {
  return CONTURI;
}

export async function obtineCont(id: string): Promise<Cont | undefined> {
  return CONTURI.find((c) => c.id === id);
}

export async function obtineBeneficiari(): Promise<Beneficiar[]> {
  return [...BENEFICIARI].sort((a, b) => Number(b.favorit) - Number(a.favorit));
}

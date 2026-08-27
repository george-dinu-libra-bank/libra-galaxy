/**
 * Date simulate — nu exista inca tabele Supabase pentru conturi (IBAN) cat timp
 * nu exista credentiale Supabase reale (doar `profiles`, `carduri`, `tranzactii`;
 * vezi lib/data/carduri.ts si lib/data/tranzactii.ts pentru datele reale).
 * Beneficiarii sunt reali, persistenti — vezi lib/data/beneficiari.ts
 * (0045_beneficiari.sql).
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

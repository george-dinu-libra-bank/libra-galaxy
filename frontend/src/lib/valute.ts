/**
 * Valutele si conversia — fara nicio dependinta de server.
 *
 * Sta separat de lib/data/curs-valutar.ts intentionat: acolo se citeste din
 * Supabase si se cheama BNR-ul, deci modulul acela trage dupa el „next/headers"
 * si nu are ce cauta in bundle-ul de client. Drawerul de schimb valutar e
 * componenta client si are nevoie doar de lucrurile de aici.
 */

/** Valutele in care se poate tine un cont. Trebuie sa fie aceleasi ca in conturi_valuta_check. */
export const VALUTE = ["RON", "EUR", "USD", "GBP", "CHF"] as const;

export type Valuta = (typeof VALUTE)[number];

/** Nume si simbol pentru interfata — sursele de curs intorc doar codul. */
export const DESPRE_VALUTA: Record<Valuta, { nume: string; simbol: string }> = {
  RON: { nume: "Leu românesc", simbol: "lei" },
  EUR: { nume: "Euro", simbol: "€" },
  USD: { nume: "Dolar american", simbol: "$" },
  GBP: { nume: "Liră sterlină", simbol: "£" },
  CHF: { nume: "Franc elvețian", simbol: "CHF" },
};

export type Curs = {
  valuta: Valuta;
  /** Cati RON face o unitate din valuta. */
  curs: number;
  /** Ziua pentru care s-a publicat cursul. */
  dataCurs: string;
  /** „BNR", sau numele sursei de rezerva. Interfata scrie exact ce scrie aici. */
  sursa: string;
};

/**
 * Converteste o suma intre doua valute, cu aceeasi formula ca public.converteste
 * din 0013_schimb_valutar.sql: prin RON, rotunjit la doi zecimali.
 *
 * Aici e doar pentru afisare — totalul de pe dashboard si previzualizarea
 * „primesti aproximativ…". Cifra care misca bani o calculeaza baza de date, la
 * cursul ei, in momentul schimbului.
 *
 * Intoarce null cand lipseste vreunul dintre cursuri: apelantul decide daca
 * ascunde randul sau il lasa afara din total — nicaieri nu inventam un curs.
 */
export function converteste(
  suma: number,
  din: Valuta,
  spre: Valuta,
  cursuri: Curs[],
): number | null {
  if (din === spre) return Math.round(suma * 100) / 100;

  const cursDin = cursuri.find((c) => c.valuta === din)?.curs;
  const cursSpre = cursuri.find((c) => c.valuta === spre)?.curs;

  if (!cursDin || !cursSpre) return null;

  return Math.round(((suma * cursDin) / cursSpre) * 100) / 100;
}

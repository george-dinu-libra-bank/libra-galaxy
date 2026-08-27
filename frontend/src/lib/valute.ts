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

/**
 * Totalul unui set de conturi, exprimat in valuta ceruta (`spre`).
 *
 * De cand conturile pot fi in valute diferite (0013_schimb_valutar.sql), o
 * simpla adunare a soldurilor ar da o cifra fara sens — 100 EUR plus 100 RON nu
 * fac 200 din nimic. Fiecare cont se aduce intai la valuta ceruta.
 *
 * Un cont a carui valuta n-are curs fata de `spre` se lasa afara din total:
 * mai bine o cifra mai mica si corecta decat una inventata.
 *
 * Statuit aici (nu in lib/data/conturi.ts) desi tipul conturilor sta acolo:
 * conturi.ts importa "@/lib/supabase/server" la nivel de modul, deci orice
 * functie exportata de acolo trage acel import in bundle-ul de client cand e
 * folosita dintr-o componenta "use client" (verificat live: build-ul Next
 * esua exact din cauza asta pentru TotalConturi).
 */
export function totalSoldIn(
  conturi: { sold: number; valuta: Valuta }[],
  cursuri: Curs[],
  spre: Valuta,
) {
  // Soldurile sunt numeric(14,2); adunarea in bani evita resturile din virgula
  // mobila (0.1 + 0.2 = 0.30000000000000004).
  const bani = conturi.reduce((total, cont) => {
    const convertit = converteste(cont.sold, cont.valuta, spre, cursuri);
    return convertit === null ? total : total + Math.round(convertit * 100);
  }, 0);

  return bani / 100;
}

/** Totalul unui set de conturi, exprimat in RON — cazul implicit al lui totalSoldIn. */
export function totalSold(conturi: { sold: number; valuta: Valuta }[], cursuri: Curs[]) {
  return totalSoldIn(conturi, cursuri, "RON");
}

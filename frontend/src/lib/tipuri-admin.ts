/**
 * Formele de date ale zonei de administrare, si etichetele lor.
 *
 * Fisierul e curat: fara acces la retea, fara `server-only`. Componentele de
 * client au nevoie de tipuri si de numele in cuvinte ale categoriilor, dar nu
 * de functiile care aduc datele — iar daca ar sta impreuna, importul unei
 * etichete ar trage dupa el tot modulul de server si build-ul ar cadea.
 */

// -----------------------------------------------------------------------------
// Verificari de identitate
// -----------------------------------------------------------------------------

/**
 * `distanta_fete` e o DISTANTA, nu o similaritate: mai mic inseamna mai
 * asemanator, iar potrivirea trece cand distanta <= prag.
 */
export type CazVerificare = {
  id: string;
  id_user: string;
  nume: string;
  email: string;
  cnp_declarat: string | null;
  cnp_extras: string | null;
  cnp_se_potriveste: boolean | null;
  distanta_fete: number | null;
  prag: number | null;
  sub_prag: boolean | null;
  status: string;
  creat_la: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  notes: string | null;
};

export type CazVerificareDetaliu = CazVerificare & {
  url_buletin: string | null;
  url_selfie: string | null;
  secunde_valabilitate: number;
};

/** Cont ramas pe verification_status='pending' — nicio dovada trimisa inca. */
export type ContNeinceput = {
  id: string;
  nume: string;
  email: string;
  creat_la: string;
};

// -----------------------------------------------------------------------------
// Tranzactii semnalate
// -----------------------------------------------------------------------------

export type ContSemnalat = {
  id_utilizator: string;
  nume: string;
  email: string;
  numar_semnalari: number;
  scor_maxim: number;
  suma_totala: number;
  tipuri: string[];
};

export type Constatare = {
  id_tranzactie: string;
  data: string;
  suma: number;
  valuta: string;
  comerciant: string;
  tip: string;
  explicatie: string;
  scor: number;
};

export type Raport = {
  id_utilizator: string;
  nume: string;
  email: string;
  iban: string;
  zile: number;
  generat_la: string;
  total_tranzactii: number;
  numar_semnalari: number;
  suma_semnalata: number;
  scor_maxim: number;
  pe_tip: Record<string, number>;
  sinteza: string | null;
  constatari: Constatare[];
};

/** Etichetele tipurilor, in cuvintele in care le-ar spune un om. */
export const ETICHETE_TIP: Record<string, string> = {
  suma_neobisnuita: "Sumă neobișnuită",
  plata_dublata: "Plată dublată",
  comerciant_nou: "Comerciant nou, sumă mare",
  rafala_de_plati: "Rafală de plăți",
  tipar_neobisnuit: "Tipar neobișnuit",
};

export function etichetaTip(tip: string): string {
  return ETICHETE_TIP[tip] ?? tip;
}

/**
 * Pragurile de gravitate, intr-un singur loc: lista, raportul si PDF-ul trebuie
 * sa spuna acelasi lucru despre acelasi scor.
 */
export function tonScor(scor: number): "grav" | "atentie" | "usor" {
  if (scor >= 10) return "grav";
  if (scor >= 5) return "atentie";
  return "usor";
}

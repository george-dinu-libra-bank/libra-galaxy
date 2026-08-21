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

// ---- Creditare ------------------------------------------------------------
//
// Sumele sosesc ca STRING, nu ca number: backendul le tine in `Decimal`, iar
// pydantic le serializeaza ca text tocmai ca sa nu treaca printr-un float pe
// drum. Se convertesc cu `Number()` la afisare, niciodata mai devreme.

export type StatusCerere =
  | "ciorna"
  | "in_analiza"
  | "oferta"
  | "analiza_manuala"
  | "respinsa"
  | "acceptata"
  | "anulata"
  | "expirata";

/** Un factor al scorecard-ului, sau un motiv de respingere pe criterii hard. */
export type MotivSauFactor = {
  cod: string;
  text?: string;
  puncte?: number;
  maxim?: number;
  explicatie?: string;
};

export type CerereCredit = {
  id: string;
  nume: string;
  status: StatusCerere;
  suma_ceruta: string;
  luni: number;
  creat_la: string;
  scor: number | null;
  dti: string | null;
  rata_lunara: string | null;
  dae: string | null;
  explicatie: string | null;
  oferta_expira_la: string | null;
  venit_folosit: string | null;
  obligatii_folosite: string | null;
  motive: MotivSauFactor[];
};

export type VerificareVenit = {
  sursa: "tranzactii" | "adeverinta" | "declarat" | "birou_credit";
  venit_constatat: string | null;
  obligatii_constatate: string | null;
  incredere: string | null;
  detalii: Record<string, unknown>;
  creat_la: string;
};

export type DocumentCerere = {
  id: string;
  tip: string;
  status: "incarcat" | "procesat" | "ilizibil" | "confirmat";
  content_type: string | null;
  marime_octeti: number | null;
  /** Ce a citit masina. Ramane neatins si dupa ce analistul corecteaza. */
  extras: {
    venit_net?: string | null;
    angajator?: string | null;
    vechime_luni?: number | null;
    incredere?: number;
    text?: string;
  };
  /** Ce a hotarat omul. Separat de `extras` dinadins — cand difera, se vede. */
  venit_confirmat: string | null;
  confirmat_la: string | null;
  /** Cand a fost sters fisierul dupa retentie. Randul ramane, documentul nu. */
  sters_la: string | null;
  creat_la: string;
  /** Link semnat, cu durata scurta. Lipseste dupa stergere. */
  url: string | null;
};

export type DosarCredit = {
  cerere: CerereCredit;
  verificari: VerificareVenit[];
  documente: DocumentCerere[];
};

export type CreditAcordat = {
  id: string;
  nume: string;
  principal: string;
  dobanda_anuala: string;
  luni: number;
  rata_lunara: string;
  dae: string | null;
  sold_ramas: string;
  data_acordarii: string;
  status: string;
  inchis_la: string | null;
};

export const ETICHETE_STATUS: Record<StatusCerere, string> = {
  ciorna: "Ciornă",
  in_analiza: "În analiză",
  oferta: "Ofertă emisă",
  analiza_manuala: "Așteaptă decizie",
  respinsa: "Respinsă",
  acceptata: "Acceptată",
  anulata: "Anulată",
  expirata: "Expirată",
};

export const ETICHETE_SURSA: Record<VerificareVenit["sursa"], string> = {
  tranzactii: "Încasări în cont",
  adeverinta: "Adeverință de venit",
  declarat: "Declarat de client",
  birou_credit: "Expuneri la alte bănci",
};

/**
 * Tonul unui status, pentru culoarea etichetei.
 *
 * `analiza_manuala` e „atentie", nu „rau": nu s-a hotarat nimic inca, doar ca
 * hotararea o ia un om. O eticheta rosie ar face un dosar in lucru sa para deja
 * pierdut, si ar impinge analistul spre respingere inainte sa se uite la el.
 */
export function tonStatus(status: StatusCerere): "bun" | "rau" | "atentie" | "neutru" {
  if (status === "oferta" || status === "acceptata") return "bun";
  if (status === "respinsa") return "rau";
  if (status === "analiza_manuala") return "atentie";
  return "neutru";
}

/** Suma din backend (string zecimal) in lei formatati romaneste. */
export function lei(valoare: string | number | null | undefined): string {
  if (valoare === null || valoare === undefined) return "—";
  return Number(valoare).toLocaleString("ro-RO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

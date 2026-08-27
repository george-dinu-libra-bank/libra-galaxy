import "server-only";

import { backendFetch } from "@/lib/backend";
import { apelBackend } from "@/lib/data/backend";

/**
 * Investigațiile de fraudă, citite din FastAPI (`/api/v1/cazuri`).
 *
 * În interfață se numesc „investigații", nu „cazuri", deși tabelele din bază
 * sunt `caz_*`: în panoul de administrare cuvântul „caz" era deja luat de
 * verificările de identitate (`decizia-cazului.tsx`), iar „dosar" de cererile
 * de credit (`fir-dosar.tsx`). Trei lucruri diferite cu același nume pe același
 * ecran ar fi fost o sursă sigură de confuzie.
 */

export type StareInvestigatie =
  | "nou"
  | "in_analiza"
  | "asteptam_clientul"
  | "client_a_raspuns"
  | "rezolvat"
  | "escalat"
  | "inchis";

export type RezultatInvestigatie = "fara_masuri" | "deblocat" | "sucursala" | "anaf";

export type Investigatie = {
  id: string;
  id_utilizator: string;
  id_administrator: string;
  stare: StareInvestigatie;
  motiv_deschidere: string;
  gravitate: number | null;
  numar_semnalari: number | null;
  rezultat: RezultatInvestigatie | null;
  deschis_la: string;
  inchis_la: string | null;
};

export type MesajInvestigatie = {
  id: string;
  autor: "banca" | "client" | "sistem";
  text: string;
  structura: Record<string, unknown>;
  propus_de_agent: boolean;
  editat_de_om: boolean;
  creat_la: string;
};

export type TranzactieInvestigatie = {
  id: string;
  suma: number;
  valuta: string;
  descriere: string | null;
  creat_la: string;
  motiv: string | null;
};

export type Dosar = {
  caz: Investigatie;
  tranzactii: TranzactieInvestigatie[];
  mesaje: MesajInvestigatie[];
};

export type Fir = {
  caz: Investigatie;
  mesaje: MesajInvestigatie[];
};

/** Câmpurile pe care extractorul le-a scos din răspunsul clientului. */
export type CampExtras = {
  intrebare: string;
  valoare: "da" | "nu" | "nu_a_spus";
  citat: string;
};

// -- administratorul ----------------------------------------------------------

export async function obtineCoada(token: string, doarDeschise = true): Promise<Investigatie[]> {
  return backendFetch<Investigatie[]>(
    `api/v1/cazuri/coada?doar_deschise=${doarDeschise}`,
    token,
  );
}

export async function obtineDosar(token: string, id: string): Promise<Dosar> {
  return backendFetch<Dosar>(`api/v1/cazuri/${encodeURIComponent(id)}`, token);
}

// -- clientul -----------------------------------------------------------------

/**
 * Investigațiile proprii. Merge prin `apelBackend`, cu sesiunea curentă, pentru
 * că ecranele clientului nu au un token de administrator la îndemână.
 */
export async function obtineInvestigatiileMele(): Promise<Investigatie[]> {
  const { date, eroare } = await apelBackend<Investigatie[]>("/api/v1/cazuri/ale-mele");
  if (eroare) throw new Error(eroare);
  return date ?? [];
}

export async function obtineFirul(id: string): Promise<Fir | null> {
  const { date, eroare } = await apelBackend<Fir>(
    `/api/v1/cazuri/${encodeURIComponent(id)}/fir`,
  );
  // Un client care nu e proprietarul primește 404, la fel ca unul care cere un
  // id inexistent: nu află că investigația există.
  if (eroare) return null;
  return date ?? null;
}

// -- etichete -----------------------------------------------------------------

export const ETICHETA_STARE: Record<StareInvestigatie, string> = {
  nou: "Nouă",
  in_analiza: "În analiză",
  asteptam_clientul: "Așteptăm clientul",
  client_a_raspuns: "Clientul a răspuns",
  rezolvat: "Rezolvată",
  escalat: "Escaladată",
  inchis: "Închisă",
};

export const ETICHETA_REZULTAT: Record<RezultatInvestigatie, string> = {
  fara_masuri: "Fără măsuri",
  deblocat: "Deblocat",
  sucursala: "Chemat la sucursală",
  anaf: "Predat conformității",
};

export const ETICHETA_VALOARE: Record<CampExtras["valoare"], string> = {
  da: "Da",
  nu: "Nu",
  nu_a_spus: "Nu a răspuns",
};

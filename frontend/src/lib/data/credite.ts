import { apelBackend } from "@/lib/data/backend";

/**
 * Citirile de creditare. Sumele vin din backend ca string (Decimal serializat),
 * ca sa nu treaca prin float pe drum — vezi backend/app/schemas/credit.py. Se
 * convertesc la number abia aici, pentru afisare.
 */

const INDISPONIBIL = "Serviciul de creditare nu este disponibil momentan.";

export type ProdusCredit = {
  slug: string;
  nume: string;
  dobandaAnuala: number;
  sumaMin: number;
  sumaMax: number;
  luniMin: number;
  luniMax: number;
  venitNetMinim: number;
};

export type RataGrafic = {
  numar: number;
  scadenta: string;
  principal: number;
  dobanda: number;
  total: number;
  soldDupa: number;
};

export type Simulare = {
  suma: number;
  luni: number;
  dobandaAnuala: number;
  rataLunara: number;
  dae: number;
  totalPlatit: number;
  costTotal: number;
  grafic: RataGrafic[];
};

export type StareCerere =
  | "ciorna"
  | "in_analiza"
  | "oferta"
  | "analiza_manuala"
  | "respinsa"
  | "acceptata"
  | "anulata"
  | "expirata";

export type CerereCredit = {
  id: string;
  status: StareCerere;
  sumaCeruta: number;
  luni: number;
  creatLa: string;
  scor: number | null;
  dti: number | null;
  rataLunara: number | null;
  dae: number | null;
  explicatie: string | null;
  ofertaExpiraLa: string | null;
};

export type StareCredit = "activ" | "restant" | "inchis" | "rambursat_anticipat";

export type Credit = {
  id: string;
  principal: number;
  dobandaAnuala: number;
  luni: number;
  rataLunara: number;
  dae: number | null;
  soldRamas: number;
  dataAcordarii: string;
  status: StareCredit;
  inchisLa: string | null;
};

export type StareRata = "programata" | "platita" | "restanta" | "anulata";

export type RataCredit = {
  numarRata: number;
  scadenta: string;
  principalRata: number;
  dobandaRata: number;
  rataTotala: number;
  soldDupa: number;
  status: StareRata;
  platitaLa: string | null;
};

export type DetaliuCredit = {
  credit: Credit;
  rate: RataCredit[];
  urmatoareaRata: RataCredit | null;
  ratePlatite: number;
};

export type CalculRambursare = {
  sold: number;
  dobandaAcumulata: number;
  totalDePlata: number;
  economieDobanda: number;
  zileDeLaUltimaScadenta: number;
};

const nr = (valoare: unknown): number => Number(valoare ?? 0);
const nrSauNull = (valoare: unknown): number | null =>
  valoare === null || valoare === undefined ? null : Number(valoare);

/** Limitele produsului — interfata nu le tine hardcodate, vin din catalog. */
export async function obtineProdusCredit(): Promise<ProdusCredit | null> {
  const { date } = await apelBackend<Record<string, unknown>>(
    "/api/v1/credite/produs",
    {},
    INDISPONIBIL,
  );
  if (!date) return null;

  return {
    slug: String(date.slug),
    nume: String(date.nume),
    dobandaAnuala: nr(date.dobanda_anuala),
    sumaMin: nr(date.suma_min),
    sumaMax: nr(date.suma_max),
    luniMin: nr(date.luni_min),
    luniMax: nr(date.luni_max),
    venitNetMinim: nr(date.venit_net_minim),
  };
}

export async function obtineCredite(): Promise<Credit[]> {
  const { date } = await apelBackend<Record<string, unknown>[]>(
    "/api/v1/credite",
    {},
    INDISPONIBIL,
  );
  return (date ?? []).map(laCredit);
}

export async function obtineDetaliuCredit(id: string): Promise<DetaliuCredit | null> {
  const { date } = await apelBackend<{
    credit: Record<string, unknown>;
    rate: Record<string, unknown>[];
    urmatoarea_rata: Record<string, unknown> | null;
    rate_platite: number;
  }>(`/api/v1/credite/${id}`, {}, INDISPONIBIL);

  if (!date) return null;

  return {
    credit: laCredit(date.credit),
    rate: (date.rate ?? []).map(laRata),
    urmatoareaRata: date.urmatoarea_rata ? laRata(date.urmatoarea_rata) : null,
    ratePlatite: nr(date.rate_platite),
  };
}

export async function obtineCereri(): Promise<CerereCredit[]> {
  const { date } = await apelBackend<Record<string, unknown>[]>(
    "/api/v1/credite/cereri",
    {},
    INDISPONIBIL,
  );
  return (date ?? []).map(laCerere);
}

export async function obtineCalculRambursare(id: string): Promise<CalculRambursare | null> {
  const { date } = await apelBackend<Record<string, unknown>>(
    `/api/v1/credite/${id}/rambursare`,
    {},
    INDISPONIBIL,
  );
  if (!date) return null;

  return {
    sold: nr(date.sold),
    dobandaAcumulata: nr(date.dobanda_acumulata),
    totalDePlata: nr(date.total_de_plata),
    economieDobanda: nr(date.economie_dobanda),
    zileDeLaUltimaScadenta: nr(date.zile_de_la_ultima_scadenta),
  };
}

export function laCredit(rand: Record<string, unknown>): Credit {
  return {
    id: String(rand.id),
    principal: nr(rand.principal),
    dobandaAnuala: nr(rand.dobanda_anuala),
    luni: nr(rand.luni),
    rataLunara: nr(rand.rata_lunara),
    dae: nrSauNull(rand.dae),
    soldRamas: nr(rand.sold_ramas),
    dataAcordarii: String(rand.data_acordarii),
    status: rand.status as StareCredit,
    inchisLa: (rand.inchis_la as string | null) ?? null,
  };
}

export function laRata(rand: Record<string, unknown>): RataCredit {
  return {
    numarRata: nr(rand.numar_rata),
    scadenta: String(rand.scadenta),
    principalRata: nr(rand.principal_rata),
    dobandaRata: nr(rand.dobanda_rata),
    rataTotala: nr(rand.rata_totala),
    soldDupa: nr(rand.sold_dupa),
    status: rand.status as StareRata,
    platitaLa: (rand.platita_la as string | null) ?? null,
  };
}

export function laCerere(rand: Record<string, unknown>): CerereCredit {
  return {
    id: String(rand.id),
    status: rand.status as StareCerere,
    sumaCeruta: nr(rand.suma_ceruta),
    luni: nr(rand.luni),
    creatLa: String(rand.creat_la),
    scor: nrSauNull(rand.scor),
    dti: nrSauNull(rand.dti),
    rataLunara: nrSauNull(rand.rata_lunara),
    dae: nrSauNull(rand.dae),
    explicatie: (rand.explicatie as string | null) ?? null,
    ofertaExpiraLa: (rand.oferta_expira_la as string | null) ?? null,
  };
}

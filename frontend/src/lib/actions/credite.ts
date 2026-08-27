"use server";

import { revalidatePath } from "next/cache";
import { apelBackend } from "@/lib/data/backend";
import type { ContractCerere, RataGrafic, Simulare } from "@/lib/data/credite";

/**
 * Mutatiile de creditare. Convenția din proiect: nu se aruncă excepții, se
 * întoarce `{ eroare?: string }` — vezi lib/actions/conturi.ts.
 *
 * Toate merg prin FastAPI, nu direct în Supabase: tabelele credit_* nu au
 * politici de scriere pentru clienți, iar deciziile trebuie luate de motorul
 * determinist din backend, nu de interfață.
 */

const INDISPONIBIL = "Serviciul de creditare nu este disponibil momentan.";

export type RezultatSimulare = { simulare?: Simulare; eroare?: string };
export type RezultatCerere = { id?: string; eroare?: string };
export type RezultatActiune = { eroare?: string };

export type Factor = { cod: string; puncte: number; maxim: number; explicatie: string };
export type Motiv = { cod: string; text: string };

export type Decizie = {
  decizie: "aprobat" | "analiza_manuala" | "respins";
  scor: number | null;
  dti: number | null;
  motive: Motiv[];
  factori: Factor[];
  explicatie: string;
  rataLunara: number | null;
  dae: number | null;
  ofertaExpiraLa: string | null;
  /**
   * Banca n-a putut confirma niciun venit din sursele ei, deci o adeverință
   * chiar ar schimba ceva. Fără semnalul ăsta, wizard-ul ar cere documente de
   * la toată lumea sau de la nimeni.
   */
  cereDocument: boolean;
};

export type RezultatDecizie = { decizie?: Decizie; eroare?: string };

const json = (corp: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(corp),
});

export async function simuleazaCredit(suma: number, luni: number): Promise<RezultatSimulare> {
  const { date, eroare } = await apelBackend<Record<string, unknown>>(
    "/api/v1/credite/simulare",
    json({ suma: String(suma), luni }),
    INDISPONIBIL,
  );

  if (eroare || !date) return { eroare: eroare ?? INDISPONIBIL };

  return {
    simulare: {
      suma: Number(date.suma),
      luni: Number(date.luni),
      dobandaAnuala: Number(date.dobanda_anuala),
      rataLunara: Number(date.rata_lunara),
      dae: Number(date.dae),
      totalPlatit: Number(date.total_platit),
      costTotal: Number(date.cost_total),
      grafic: ((date.grafic as Record<string, unknown>[]) ?? []).map(
        (rata): RataGrafic => ({
          numar: Number(rata.numar),
          scadenta: String(rata.scadenta),
          principal: Number(rata.principal),
          dobanda: Number(rata.dobanda),
          total: Number(rata.total),
          soldDupa: Number(rata.sold_dupa),
        }),
      ),
    },
  };
}

export type DateCerere = {
  suma: number;
  luni: number;
  venitDeclarat: number;
  angajator: string;
  vechimeAngajatorLuni: number;
  obligatiiDeclarate: number;
  scop?: string;
};

export async function depuneCerere(date: DateCerere): Promise<RezultatCerere> {
  const { date: raspuns, eroare } = await apelBackend<{ id: string }>(
    "/api/v1/credite/cereri",
    json({
      suma: String(date.suma),
      luni: date.luni,
      venit_declarat: String(date.venitDeclarat),
      angajator: date.angajator,
      vechime_angajator_luni: date.vechimeAngajatorLuni,
      obligatii_declarate: String(date.obligatiiDeclarate),
      scop: date.scop,
      consimtamant: true,
    }),
    INDISPONIBIL,
  );

  if (eroare || !raspuns) return { eroare: eroare ?? INDISPONIBIL };
  return { id: raspuns.id };
}

export async function evalueazaCerere(idCerere: string): Promise<RezultatDecizie> {
  const { date, eroare } = await apelBackend<Record<string, unknown>>(
    `/api/v1/credite/cereri/${idCerere}/evalueaza`,
    { method: "POST" },
    INDISPONIBIL,
  );

  if (eroare || !date) return { eroare: eroare ?? INDISPONIBIL };

  return {
    decizie: {
      decizie: date.decizie as Decizie["decizie"],
      scor: date.scor === null ? null : Number(date.scor),
      dti: date.dti === null ? null : Number(date.dti),
      motive: (date.motive as Motiv[]) ?? [],
      factori: (date.factori as Factor[]) ?? [],
      explicatie: String(date.explicatie ?? ""),
      rataLunara: date.rata_lunara === null ? null : Number(date.rata_lunara),
      dae: date.dae === null ? null : Number(date.dae),
      ofertaExpiraLa: (date.oferta_expira_la as string | null) ?? null,
      cereDocument: date.cere_document === true,
    },
  };
}


export type RezultatDocument = {
  eroare?: string;
  /** Ce a citit sistemul din document. Null când n-a putut citi nimic. */
  venitCitit?: number | null;
  angajator?: string | null;
};

/**
 * Încarcă adeverința de venit.
 *
 * Trimiterea e multipart, nu JSON, dar trece tot prin `apelBackend`: acela nu
 * impune `Content-Type` (o face helperul `json()`, folosit de celelalte
 * acțiuni), deci `fetch` pune singur granița multipart. Antetul nu se setează
 * de mână nicăieri aici — scris manual, ar rupe granița.
 *
 * Ce se întoarce e informativ: documentul e citit, nu crezut. Cifra nu intră în
 * decizie până n-o confirmă un analist.
 */
/**
 * Raspunsul clientului in firul dosarului.
 *
 * Exista ca sa aiba unde intreba cand nu intelege ce act i se cere — pana acum
 * singura lui actiune era sa incarce un fisier si sa spere ca e cel bun.
 */
export async function trimiteMesajCerere(
  idCerere: string,
  text: string,
): Promise<{ eroare?: string }> {
  // `json()`, nu un POST scris de mana: `apelBackend` NU pune `Content-Type`
  // (ca sa mearga si pentru FormData la incarcarea documentelor), iar fara el
  // FastAPI nu poate parsa corpul si raspunde 422 — adica "eroare neasteptata"
  // in ecran, fara nimic in consola.
  const { eroare } = await apelBackend<Record<string, unknown>>(
    `/api/v1/credite/cereri/${encodeURIComponent(idCerere)}/mesaje`,
    json({ text }),
    INDISPONIBIL,
  );

  if (eroare) return { eroare };

  revalidatePath("/credite");
  return {};
}


/** Firul a fost deschis — mesajele bancii nu mai sunt necitite. */
export async function marcheazaFirulCitit(idCerere: string): Promise<{ eroare?: string }> {
  const { eroare } = await apelBackend(
    `/api/v1/credite/cereri/${encodeURIComponent(idCerere)}/mesaje/citite`,
    { method: "POST" },
    INDISPONIBIL,
  );

  if (eroare) return { eroare };

  revalidatePath("/credite");
  revalidatePath("/dashboard");
  return {};
}


/**
 * Clientul isi retrage cererea.
 *
 * Nu e doar curatenie de ecran: inchiderea completeaza `finalizat_la` in
 * backend, deci porneste retentia documentelor. Fara ea, un dosar abandonat isi
 * tinea adeverinta in bucket la nesfarsit.
 */
export async function anuleazaCerere(idCerere: string): Promise<RezultatActiune> {
  const { eroare } = await apelBackend(
    `/api/v1/credite/cereri/${encodeURIComponent(idCerere)}/anuleaza`,
    { method: "POST" },
    INDISPONIBIL,
  );

  if (eroare) return { eroare };

  revalidatePath("/credite");
  revalidatePath("/dashboard");
  return {};
}

export async function incarcaAdeverinta(
  idCerere: string,
  formular: FormData,
): Promise<RezultatDocument> {
  const fisier = formular.get("fisier");
  if (!(fisier instanceof File) || fisier.size === 0) {
    return { eroare: "Alege un fișier." };
  }

  const { date, eroare } = await apelBackend<Record<string, unknown>>(
    `/api/v1/credite/cereri/${idCerere}/documente`,
    { method: "POST", body: formular },
    INDISPONIBIL,
  );

  if (eroare || !date) return { eroare: eroare ?? INDISPONIBIL };

  const extras = (date.extras as Record<string, unknown>) ?? {};
  return {
    venitCitit: extras.venit_net ? Number(extras.venit_net) : null,
    angajator: (extras.angajator as string | null) ?? null,
  };
}

/**
 * Semnarea ofertei.
 *
 * `contractCitit` nu e o formalitate de interfata: backendul refuza semnatura
 * fara el (`AcceptaRequest`), deci un buton dezactivat in browser nu e singura
 * plasa. `derulat` (0..1) spune cat a parcurs clientul din text si ramane in
 * `semnatura`, pe randul din `credite`.
 */
export async function acceptaOferta(
  idCerere: string,
  idCont: string,
  contractCitit: boolean,
  derulat: number,
): Promise<RezultatActiune> {
  const { eroare } = await apelBackend(
    `/api/v1/credite/cereri/${idCerere}/accepta`,
    json({
      id_cont: idCont,
      contract_citit: contractCitit,
      contract_derulat: Math.min(1, Math.max(0, derulat)),
    }),
    INDISPONIBIL,
  );

  if (eroare) return { eroare };

  // Banii au intrat in cont: se schimba si dashboard-ul, si istoricul.
  revalidatePath("/credite");
  revalidatePath("/dashboard");
  revalidatePath("/istoric");
  return {};
}

export async function ramburseazaAnticipat(
  idCredit: string,
  suma?: number,
): Promise<RezultatActiune> {
  const { eroare } = await apelBackend(
    `/api/v1/credite/${idCredit}/rambursare`,
    json({ suma: suma === undefined ? null : String(suma) }),
    INDISPONIBIL,
  );

  if (eroare) return { eroare };

  revalidatePath("/credite");
  revalidatePath(`/credite/${idCredit}`);
  revalidatePath("/dashboard");
  revalidatePath("/istoric");
  return {};
}

/**
 * Muta scadentele inainte si incaseaza ratele pana acolo.
 *
 * Nu e o unealta de productie: exista ca sa se poata vedea rambursarea
 * functionand fara sa astepti o luna intre rate. Foloseste acelasi RPC ca
 * procesarea obisnuita, deci nu falsifica nimic — doar grabeste ceasul.
 */
export async function avanseazaTimp(idCredit: string, luni: number): Promise<RezultatActiune> {
  const { eroare } = await apelBackend(
    `/api/v1/credite/${idCredit}/avanseaza-timp?luni=${luni}`,
    { method: "POST" },
    INDISPONIBIL,
  );

  if (eroare) return { eroare };

  revalidatePath("/credite");
  revalidatePath(`/credite/${idCredit}`);
  revalidatePath("/dashboard");
  return {};
}


/**
 * Contractul unei oferte, pentru wizard-ul de cerere.
 *
 * Ecranul lui e o componenta de client, deci nu poate chema direct citirile din
 * `lib/data` — trece printr-o actiune de server, ca restul.
 */
export async function obtineContractPentruOferta(
  idCerere: string,
): Promise<{ contract?: ContractCerere; eroare?: string }> {
  const { date, eroare } = await apelBackend<Record<string, unknown>>(
    `/api/v1/credite/cereri/${encodeURIComponent(idCerere)}/contract`,
    {},
    INDISPONIBIL,
  );
  if (eroare || !date) return { eroare: eroare ?? INDISPONIBIL };

  return {
    contract: {
      idCerere: String(date.id_cerere ?? idCerere),
      html: String(date.html ?? ""),
      trimisLa: (date.trimis_la as string | null) ?? null,
    },
  };
}

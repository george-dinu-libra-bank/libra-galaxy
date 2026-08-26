import { backendFetch } from "@/lib/backend";

/**
 * Cererile de inchidere a unui CONT BANCAR, pentru analist.
 *
 * Alta operatiune decat `admin-stergeri.ts`, si se confunda usor: acolo pleaca
 * omul din banca, aici se inchide un singur cont bancar si omul ramane client.
 *
 * `destinatii` vine gata filtrata din backend — doar conturile deschise, altele
 * decat cel care se inchide. O lista din care lipsesc optiunile imposibile e mai
 * buna decat una in care sunt afisate si dezactivate.
 */

export type ContAdmin = {
  id: string;
  nume: string | null;
  sold: string;
  valuta: string | null;
  blocat: boolean;
  inchis: boolean;
  este_principal: boolean;
};

export type CardInchis = {
  id: string;
  ultimele4: string;
  tip: string | null;
};

export type CerereInchidere = {
  id: string;
  id_utilizator: string;
  id_cont: string;
  id_cont_destinatie: string | null;
  nume: string | null;
  email: string | null;
  motiv: string | null;
  status: string;
  creat_la: string;
  decis_la: string | null;
  motiv_refuz: string | null;
  cont: ContAdmin | null;
  destinatii: ContAdmin[];
  carduri: CardInchis[];
};

export async function obtineCereriInchidere(token: string): Promise<CerereInchidere[]> {
  return backendFetch<CerereInchidere[]>("api/v1/admin/cereri-inchidere-cont", token);
}

/**
 * Destinatia din care porneste analistul: propunerea clientului daca mai e
 * valida, altfel contul principal, altfel primul deschis.
 *
 * Propunerea poate sa nu mai fie valida — contul ales de client putea fi inchis
 * intre timp — de aceea se cauta in `destinatii`, nu se foloseste id-ul brut.
 */
export function destinatiaImplicita(cerere: CerereInchidere): ContAdmin | null {
  const propusa = cerere.destinatii.find((c) => c.id === cerere.id_cont_destinatie);
  if (propusa) return propusa;
  return cerere.destinatii.find((c) => c.este_principal) ?? cerere.destinatii[0] ?? null;
}

/** De ce nu se poate aproba, in cuvinte — ca butonul dezactivat sa nu fie mut. */
export function motiveleBlocarii(cerere: CerereInchidere): string[] {
  const motive: string[] = [];
  const cont = cerere.cont;
  if (!cont) return ["Contul nu mai există."];

  if (cont.este_principal) {
    motive.push("E contul principal al clientului; acesta nu se poate închide.");
  }
  if (cont.blocat) {
    motive.push("Contul e blocat administrativ; se lămurește întâi blocarea.");
  }
  if (Number(cont.sold) < 0) {
    motive.push("Contul are sold negativ; se acoperă înainte de închidere.");
  }
  if (Number(cont.sold) > 0 && cerere.destinatii.length === 0) {
    motive.push("Are sold, dar clientul nu mai are alt cont deschis în care să fie mutat.");
  }
  return motive;
}

export function sePoateAproba(cerere: CerereInchidere): boolean {
  return cerere.status === "in_asteptare" && motiveleBlocarii(cerere).length === 0;
}

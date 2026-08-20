/**
 * Vocabularul comun al platilor: stari, forma randului si maparea catre
 * interfata.
 *
 * Fisierul e deliberat curat de orice import de server (fara „next/headers"):
 * il folosesc si Server Components, si hook-urile din browser, care primesc
 * acelasi rand prin Realtime.
 */

export type StarePlata =
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "DECLINED"
  | "EXPIRED"
  | "FAILED";

/** Randul din public.payments, asa cum vine din PostgREST si din Realtime. */
export type RandPlata = {
  id: string;
  id_user: string;
  suma: string | number;
  valuta: string;
  comerciant: string;
  descriere: string | null;
  card_ultimele4: string;
  status: string;
  motiv?: string | null;
  expira_la: string | null;
};

/** O plata care asteapta confirmarea, asa cum o vede drawerul din aplicatie. */
export type PlataInAsteptare = {
  id: string;
  suma: number;
  valuta: string;
  comerciant: string;
  descriere: string | null;
  /** „•••• 4242" — ultimele patru cifre sunt denormalizate in public.payments. */
  cardMascat: string;
  expiraLa: string | null;
};

export function laPlataInAsteptare(rand: RandPlata): PlataInAsteptare {
  return {
    id: rand.id,
    suma: Number(rand.suma),
    valuta: rand.valuta,
    comerciant: rand.comerciant,
    descriere: rand.descriere,
    cardMascat: `•••• ${rand.card_ultimele4}`,
    expiraLa: rand.expira_la,
  };
}

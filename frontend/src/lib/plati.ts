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
  /** Contul debitat, adus prin relatia payments.id_cont. Lipseste in Realtime. */
  conturi_bancare?: { nume: string; valuta: string } | null;
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
  /**
   * Contul din care se ia suma. De cand fiecare card apartine unui cont (0027),
   * omul trebuie sa vada ce cont se goleste, nu doar ce card se foloseste:
   * ultimele patru cifre nu mai spun de unde pleaca banii.
   */
  numeCont: string | null;
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
    numeCont: rand.conturi_bancare?.nume ?? null,
    expiraLa: rand.expira_la,
  };
}

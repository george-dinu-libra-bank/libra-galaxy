/**
 * Tipurile si regulile pure pentru cererile de inchidere a contului —
 * separate de `lib/data/admin-stergeri.ts` (care importa `lib/backend.ts`,
 * server-only) ca sa poata fi importate si dintr-o componenta client
 * (`components/admin/cereri-stergere.tsx`) fara sa traga dupa ele granita
 * server/client. Acelasi tipar ca `lib/valute.ts` vs `lib/data/conturi.ts`.
 */

export type ContClient = {
  nume: string | null;
  sold: string;
  valuta: string | null;
  blocat: boolean;
};

export type CerereStergere = {
  id: string;
  id_utilizator: string;
  nume: string | null;
  email: string | null;
  motiv: string | null;
  status: string;
  creat_la: string;
  decis_la: string | null;
  motiv_refuz: string | null;
  conturi: ContClient[];
  credite_in_derulare: number;
};

/** Toate conturile pe zero, fara blocari si fara credite — vezi 0038. */
export function sePoateSterge(cerere: CerereStergere): boolean {
  return (
    cerere.status === "aprobata" &&
    cerere.credite_in_derulare === 0 &&
    cerere.conturi.every((cont) => Number(cont.sold) === 0 && !cont.blocat)
  );
}

/** De ce nu se poate, in cuvinte — ca butonul dezactivat sa nu fie mut. */
export function motiveleBlocarii(cerere: CerereStergere): string[] {
  const motive: string[] = [];

  if (cerere.status !== "aprobata") {
    motive.push("Cererea trebuie aprobată întâi.");
  }
  if (cerere.credite_in_derulare > 0) {
    motive.push(`Are ${cerere.credite_in_derulare} credit(e) în derulare.`);
  }

  const cuBani = cerere.conturi.filter((cont) => Number(cont.sold) !== 0);
  if (cuBani.length > 0) {
    motive.push(
      `Are sold în ${cuBani.length} cont(uri): ` +
        cuBani.map((c) => `${c.nume ?? "Cont"} ${c.sold} ${c.valuta ?? ""}`.trim()).join(", ") +
        ".",
    );
  }

  const blocate = cerere.conturi.filter((cont) => cont.blocat);
  if (blocate.length > 0) {
    motive.push(`Are ${blocate.length} cont(uri) blocate administrativ.`);
  }

  return motive;
}

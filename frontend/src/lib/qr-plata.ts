/**
 * Cererea de plata dintr-un cod QR.
 *
 * Codul QR nu contine bani si nu declanseaza nimic singur: in el sta doar un
 * link catre ecranul de transfer al aplicatiei, cu contul, suma si descrierea
 * puse ca parametri. Cine il scaneaza ajunge pe /transfer cu campurile deja
 * completate si confirma el plata — pasul de confirmare ramane al lui.
 *
 * De aceea codul nici nu se salveaza nicaieri: e generat integral din link, deci
 * poate fi refacut oricand, identic, din aceleasi trei valori.
 *
 * Fisierul e pur (fara Supabase, fara Next), fiindca il folosesc si ecranul care
 * genereaza codul, in browser, si pagina de transfer, pe server.
 */

/** Lungimea maxima a descrierii, aceeasi cu a campului „Detalii" din formular. */
const MAXIM_DETALII = 140;

export type CerereDePlata = {
  /** Contul in care se cer banii. */
  iban: string;
  /** Suma ceruta, sau null cand cel care cere lasa suma la latitudinea celuilalt. */
  suma: number | null;
  detalii: string | null;
};

/** Forma unui IBAN emis de banca (0001_profiles.sql). Cifrele de control se verifica pe server. */
const FORMAT_IBAN = /^RO[0-9]{2}[A-Z0-9]{20}$/;

export function normalizeazaIban(iban: string): string {
  return iban.replace(/\s+/g, "").toUpperCase();
}

/**
 * Linkul care ajunge in codul QR.
 *
 * `origine` vine de la apelant (`window.location.origin`), fiindca adresa
 * publica a aplicatiei difera intre laptop, telefon si productie, iar un link
 * relativ n-ar insemna nimic pentru camera altui telefon.
 */
export function construiesteLinkPlata(origine: string, cerere: CerereDePlata): string {
  const params = new URLSearchParams({ iban: normalizeazaIban(cerere.iban) });

  // Punct la zecimale, nu virgula: valoarea trece printr-un URL si e citita
  // inapoi cu Number(), care nu stie de scrierea romaneasca.
  if (cerere.suma && cerere.suma > 0) params.set("suma", cerere.suma.toFixed(2));
  if (cerere.detalii?.trim()) params.set("detalii", cerere.detalii.trim());

  return `${origine.replace(/\/+$/, "")}/transfer?${params.toString()}`;
}

/**
 * Citeste cererea din parametrii unui URL. Intoarce null daca IBAN-ul lipseste
 * sau nu are forma buna — restul campurilor sunt optionale si se ignora tacut
 * cand sunt aiurea, ca un link stricat sa nu blocheze ecranul de transfer.
 */
export function citesteCerereDePlata(params: {
  iban?: string;
  suma?: string;
  detalii?: string;
}): CerereDePlata | null {
  const iban = normalizeazaIban(params.iban ?? "");
  if (!FORMAT_IBAN.test(iban)) return null;

  const suma = Number((params.suma ?? "").replace(",", "."));

  return {
    iban,
    suma: Number.isFinite(suma) && suma > 0 ? Number(suma.toFixed(2)) : null,
    detalii: params.detalii?.trim().slice(0, MAXIM_DETALII) || null,
  };
}

/**
 * Generare de IBAN romanesc (ISO 13616) pentru contul curent deschis la inregistrare.
 * Se ruleaza DOAR pe server (server action), niciodata in browser: valoarea ajunge in
 * user_metadata, de unde trigger-ul din Postgres o copiaza in public.profiles.
 */

const COD_TARA = "RO";
const COD_BANCA = "LIBR";

/** Restul impartirii la 97 pentru un sir lung de cifre, calculat pe bucati. */
function mod97(cifre: string): number {
  let rest = 0;

  for (const cifra of cifre) {
    rest = (rest * 10 + Number(cifra)) % 97;
  }

  return rest;
}

/** A=10 ... Z=35, conform ISO 13616. */
function litereInCifre(text: string): string {
  return text
    .toUpperCase()
    .split("")
    .map((ch) =>
      /[0-9]/.test(ch) ? ch : (ch.charCodeAt(0) - 55).toString(),
    )
    .join("");
}

/** Verifica cifrele de control ale unui IBAN. */
export function ibanEsteValid(iban: string): boolean {
  const curat = iban.replace(/\s+/g, "").toUpperCase();

  if (!/^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$/.test(curat)) return false;

  const rearanjat = curat.slice(4) + curat.slice(0, 4);

  return mod97(litereInCifre(rearanjat)) === 1;
}

/** Genereaza un IBAN valid: RO + cifre de control + LIBR + 16 cifre. */
export function genereazaIban(): string {
  const numarCont = Array.from({ length: 16 }, () =>
    Math.floor(Math.random() * 10),
  ).join("");

  const bban = `${COD_BANCA}${numarCont}`;
  const control = 98 - mod97(litereInCifre(`${bban}${COD_TARA}00`));

  return `${COD_TARA}${String(control).padStart(2, "0")}${bban}`;
}

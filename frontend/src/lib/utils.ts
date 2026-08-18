import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Compune clase Tailwind, ultima castiga in caz de conflict. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** RO49AAAA1B31007593840000 -> "RO49 AAAA 1B31 0075 9384 0000" */
export function formateazaIban(iban: string) {
  return iban.replace(/\s+/g, "").replace(/(.{4})/g, "$1 ").trim();
}

/** 1900101123456 -> "1•••••••••456" */
export function mascheazaCnp(cnp: string) {
  if (cnp.length !== 13) return "•".repeat(13);
  return `${cnp[0]}${"•".repeat(9)}${cnp.slice(-3)}`;
}

/** 1250.5 -> "1.250,50 RON" (DESIGN.md 11) */
export function formateazaSuma(suma: number, valuta = "RON") {
  const numar = new Intl.NumberFormat("ro-RO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(suma);
  return `${numar} ${valuta}`;
}

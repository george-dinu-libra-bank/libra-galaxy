export const TEMA_COOKIE = "libra-tema";

export type Tema = "light" | "dark";

const UN_AN_IN_SECUNDE = 60 * 60 * 24 * 365;

/** Normalizeaza valoarea bruta a cookie-ului la o tema valida. */
export function temaDinCookie(valoare: string | undefined): Tema {
  return valoare === "dark" ? "dark" : "light";
}

export function citesteTema(): Tema {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/**
 * Salveaza tema intr-un cookie (nu in localStorage) ca sa o poata citi si
 * layout-ul de pe server — asa clasa .dark ajunge in HTML-ul initial si nu mai
 * avem nevoie de un script inline in <head> care sa o puna inainte de paint.
 */
export function aplicaTema(tema: Tema) {
  document.documentElement.classList.toggle("dark", tema === "dark");
  document.cookie = `${TEMA_COOKIE}=${tema}; path=/; max-age=${UN_AN_IN_SECUNDE}; samesite=lax`;
}

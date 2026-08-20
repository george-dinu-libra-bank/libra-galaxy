export const TEMA_STORAGE_KEY = "libra-tema";

export type Tema = "light" | "dark";

/** Scriptul inline din <head> foloseste aceeasi logica, in JS simplu (fara import). */
export const SCRIPT_INITIALIZARE_TEMA = `
(function () {
  try {
    var tema = localStorage.getItem("${TEMA_STORAGE_KEY}");
    if (tema === "dark") document.documentElement.classList.add("dark");
  } catch (e) {}
})();
`;

export function citesteTema(): Tema {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function aplicaTema(tema: Tema) {
  document.documentElement.classList.toggle("dark", tema === "dark");
  try {
    localStorage.setItem(TEMA_STORAGE_KEY, tema);
  } catch {
    // localStorage poate fi indisponibil (mod privat) — tema tot se aplica pentru sesiunea curenta.
  }
}

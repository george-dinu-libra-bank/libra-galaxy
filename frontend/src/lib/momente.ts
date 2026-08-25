/**
 * Formatarea momentelor, la fel pe server si in browser.
 *
 * `toLocaleString` fara `timeZone` foloseste fusul masinii pe care ruleaza:
 * containerul e pe UTC, browserul e pe ora Romaniei. Diferenta apare in HTML si
 * Next o raporteaza ca nepotrivire de hidratare, iar omul vede o ora care sare
 * la incarcare. Fusul fixat aici rezolva amandoua, si e oricum cel corect
 * pentru o banca romaneasca.
 */

const FUS = "Europe/Bucharest";

export function dataSiOra(moment: string): string {
  return new Date(moment).toLocaleString("ro-RO", {
    timeZone: FUS,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function dataLunga(moment: string): string {
  return new Date(moment).toLocaleString("ro-RO", {
    timeZone: FUS,
    day: "2-digit",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}

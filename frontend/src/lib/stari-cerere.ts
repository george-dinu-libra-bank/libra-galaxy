/**
 * Starile unei cereri decise de banca, si cum arata ele pe ecran.
 *
 * Aceleasi patru stari la cererea de inchidere a relatiei (0036) si la cea de
 * inchidere a unui cont bancar (0040) — aceleasi cuvinte, aceleasi culori. Erau
 * scrise de doua ori; aici sunt o data.
 *
 * „retrasa" e a clientului (s-a razgandit), „respinsa" e a bancii. Doua cuvinte
 * diferite fiindca sunt doua lucruri diferite in jurnal.
 */

export type StareCerere = "in_asteptare" | "aprobata" | "respinsa" | "retrasa";

export const ETICHETE_STARE: Record<string, { text: string; clasa: string }> = {
  in_asteptare: { text: "În așteptare", clasa: "bg-warning/10 text-warning" },
  aprobata: { text: "Aprobată", clasa: "bg-success/10 text-success" },
  respinsa: { text: "Respinsă", clasa: "bg-danger/10 text-danger" },
  retrasa: { text: "Retrasă de client", clasa: "bg-muted text-ink-faint" },
};

/** Starea necunoscuta nu strica pagina: se arata asa cum a venit din bază. */
export function etichetaStare(status: string) {
  return ETICHETE_STARE[status] ?? { text: status, clasa: "bg-muted text-ink-faint" };
}

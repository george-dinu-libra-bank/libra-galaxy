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

/** 1250.5 -> "1.250,50" — fara valuta, pentru cand se afiseaza separat (ex. buton). */
export function formateazaNumar(suma: number) {
  return new Intl.NumberFormat("ro-RO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(suma);
}

/** 1250.5 -> "1.250,50 RON" (DESIGN.md 11) */
export function formateazaSuma(suma: number, valuta = "RON") {
  return `${formateazaNumar(suma)} ${valuta}`;
}

// Fus orar fixat explicit: serverul (container, de regula UTC) si browserul
// clientului (ora locala a utilizatorului) calculeaza altfel ora/ziua daca
// lasam Intl sa foloseasca fusul sistemului, ceea ce produce hydration
// mismatch la SSR (ora afisata difera intre randarea server si client).
const FUS_ORAR = "Europe/Bucharest";

/** 2024-05-01T12:05:00Z -> "12:05" (Europe/Bucharest) */
export function formateazaOra(data: string | Date) {
  return new Date(data).toLocaleTimeString("ro-RO", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: FUS_ORAR,
  });
}

/** Ziua calendaristica in Europe/Bucharest, ca sir "AAAA-LL-ZZ" comparabil. */
function ziISO(data: string | Date) {
  return new Date(data).toLocaleDateString("en-CA", { timeZone: FUS_ORAR });
}

/** Eticheteaza o data drept "Astăzi" / "Ieri" sau "1 mai", relativ la Europe/Bucharest. */
export function etichetaZi(data: string | Date) {
  const ziua = new Date(data);
  const astazi = new Date();

  if (ziISO(ziua) === ziISO(astazi)) return "Astăzi";

  const ieri = new Date(astazi);
  ieri.setDate(ieri.getDate() - 1);
  if (ziISO(ziua) === ziISO(ieri)) return "Ieri";

  return ziua.toLocaleDateString("ro-RO", { day: "numeric", month: "long", timeZone: FUS_ORAR });
}

import "server-only";

import { headers } from "next/headers";

/**
 * De unde a venit cererea, pentru detecția de neregularități.
 *
 * Se citește din antetele pe care le pune reverse proxy-ul. Cât de mult poți
 * avea încredere în valoare depinde de ce stă în fața aplicației:
 *
 * - în spatele unui proxy propriu (Vercel, nginx configurat), `x-forwarded-for`
 *   e rescris de proxy și nu poate fi falsificat de client;
 * - expus direct, oricine poate trimite ce antet vrea.
 *
 * De aceea IP-ul e un semnal, nu o dovadă: ridică o întrebare pentru un om, nu
 * blochează singur pe nimeni. Un client cu VPN produce exact același tipar ca
 * unul care își falsifică antetul.
 *
 * `x-forwarded-for` poate conține un lanț („client, proxy1, proxy2"); primul e
 * cel mai apropiat de client, deci acela se ia.
 */
export async function ipCerere(): Promise<string | null> {
  const h = await headers();

  const lant = h.get("x-forwarded-for");
  if (lant) {
    const primul = lant.split(",")[0]?.trim();
    if (primul && esteIpValid(primul)) return primul;
  }

  const direct = h.get("x-real-ip")?.trim();
  if (direct && esteIpValid(direct)) return direct;

  return null;
}

/**
 * Verificare de formă, nu de rutabilitate.
 *
 * Coloana din baza e `inet`, care respinge orice nu e o adresă validă — iar o
 * eroare de bază de date la o plată reușită ar fi absurdă: plata a mers, doar
 * n-am putut nota de unde. Filtrăm aici ca să nu ajungem acolo.
 */
function esteIpValid(valoare: string): boolean {
  // IPv4 simplu, cu octeți în interval.
  const v4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(valoare);
  if (v4) {
    return v4.slice(1).every((o) => Number(o) <= 255);
  }

  // IPv6: destul cât să respingem text arbitrar, fără să reimplementăm RFC-ul.
  return /^[0-9a-fA-F:]+$/.test(valoare) && valoare.includes(":");
}
